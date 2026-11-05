"""The check before any installation, run as itself against a directory standing in for the machine."""

import importlib.machinery
import importlib.util
import json
import re
import subprocess
import time
from pathlib import Path

import pytest

ROLE = Path(__file__).parents[3] / "roles" / "check" / "files"
SCRIPT = ROLE / "porelo-host-check"
LIMITS = json.loads((ROLE / "limits.json").read_text())
CPUINFO = Path(__file__).parent / "cpuinfo"


def machine(root, changes=None):
    """A machine that passes everything, but for what the test changes; None removes a file."""
    files = {
        "euid": "0",
        "etc/os-release": 'ID=ubuntu\nVERSION_ID="26.04"\n',
        "proc/cpuinfo": "".join(f"processor : {n}\n" for n in range(4)) + "flags : fpu sse\n",
        "proc/meminfo": "MemTotal: 8192000 kB\n",
        "proc/net/route": "Iface Destination Gateway Flags Ref Use Metric Mask\neth0 00000000 0101A8C0 3 0 0 0 00000000\n",
        "route_address": "192.0.2.5",
        "proc/net/tcp": "sl local rem st\n0: 00000000:0016 00000000:0000 0A\n",
        "sys/fs/cgroup/cgroup.controllers": "cpuset cpu io memory pids\n",
        "delegated": "cpu memory pids\n",
        "etc/ssh/ssh_host_ed25519_key.pub": "ssh-ed25519 AAAA host\n",
    }
    files.update(changes or {})
    for name, text in files.items():
        if text is not None:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    (root / "var" / "lib").mkdir(parents=True, exist_ok=True)
    (root / "home").mkdir(exist_ok=True)
    return root


def ask(root, **choices):
    """Runs the check and returns its exit code, its answer and its findings by id."""
    done = subprocess.run(
        ["python3", str(SCRIPT), "--root", str(root), "--no-network", "--choices", json.dumps(choices)],
        capture_output=True,
        text=True,
        check=False,
    )
    answer = json.loads(done.stdout)
    return done.returncode, answer, {row["id"]: row for row in answer["findings"]}


def test_a_machine_with_all_it_needs_passes_and_says_what_it_could_not_ask(tmp_path):
    code, answer, found = ask(machine(tmp_path), kvm=False, forge=True)
    assert code == 0 and answer["ok"] and answer["complete"], answer
    assert answer["v"] == 1
    assert found["reach_fuinorg.jfrog.io"]["state"] == "unknown"
    assert found["reach_codeberg.org"]["state"] == "unknown"
    assert found["address"]["found"] == "192.0.2.5"


def test_every_lack_is_named_at_once_with_its_value_what_was_asked_and_what_to_do(tmp_path):
    code, answer, found = ask(
        machine(
            tmp_path,
            {"euid": "1000", "etc/os-release": 'ID=debian\nVERSION_ID="12"\n', "proc/net/route": "Iface Destination\n"},
        ),
        kvm=True,
        forge=True,
        jobs=9,
    )
    assert code == 1 and not answer["ok"] and answer["complete"], answer
    failed = {name for name, row in found.items() if row["state"] == "fail"}
    assert {"root", "system", "virtualization", "route", "jobs"} <= failed, failed
    assert found["root"]["found"] == 1000 and found["root"]["asked"] == 0
    assert found["system"]["found"] == "debian 12" and found["system"]["asked"] == "ubuntu 26.04"
    assert found["virtualization"]["do"]
    assert found["route"]["do"]


@pytest.mark.parametrize(
    ("flags", "holds"),
    [("amd-ryzen-svm-lock.txt", True), ("intel-vmx.txt", True), ("none-but-svm-lock.txt", False)],
)
def test_the_cpu_is_asked_only_of_a_host_that_wants_kvm(tmp_path, flags, holds):
    root = machine(tmp_path)
    (root / "proc" / "cpuinfo").write_text((CPUINFO / flags).read_text())
    _, _, wanted = ask(root, kvm=True)
    assert wanted["virtualization"]["state"] == ("pass" if holds else "fail"), wanted["virtualization"]
    _, _, unwanted = ask(root, kvm=False)
    assert "virtualization" not in unwanted


def test_a_pool_without_kvm_and_one_too_large_are_both_named(tmp_path):
    code, _, found = ask(
        machine(tmp_path), kvm=False, forge=True, pool={"systems": ["ubuntu"], "accounts": 8, "memory": 8192}
    )
    assert code == 1
    assert found["pool_kvm"]["state"] == "fail" and found["pool_memory"]["state"] == "fail"
    assert found["pool_shape"]["state"] == "pass"


def test_a_taken_port_fails_also_as_words_but_not_the_one_this_hosts_own_forge_holds(tmp_path):
    root = machine(tmp_path)
    assert ask(root, ports=[22, 3001])[2]["ports"]["found"] == [22]
    assert ask(root, ports=["22"])[2]["ports"]["found"] == [22]
    (root / "etc" / "porelo-host").mkdir(parents=True)
    (root / "etc" / "porelo-host" / "forge.conf").write_text("account=porelo-forge\ngit_port=22\n")
    assert ask(root, ports=[22])[2]["ports"]["state"] == "pass"
    (root / "etc" / "porelo-host" / "forge.conf").write_text("account=porelo-forge\ngit_port=3001\n")
    assert ask(root, ports=[22])[2]["ports"]["found"] == [22]


def test_a_route_with_a_zero_destination_and_a_mask_is_no_default_route(tmp_path):
    table = "Iface Destination Gateway Flags Ref Use Metric Mask\neth0 00000000 0101A8C0 3 0 0 0 00000080\n"
    _, _, found = ask(machine(tmp_path, {"proc/net/route": table}))
    assert found["route"]["state"] == "fail"
    assert "address" not in found


def test_a_default_route_with_no_address_fails(tmp_path):
    _, _, found = ask(machine(tmp_path, {"route_address": ""}))
    assert found["address"]["state"] == "fail"


def test_each_package_source_is_asked_on_its_own_port_in_either_form(tmp_path):
    root = machine(
        tmp_path,
        {
            "etc/apt/sources.list.d/a.sources": "URIs: https://mirror.example/ubuntu\nTypes: deb\n",
            "etc/apt/sources.list.d/b.sources": "URIs: http://plain.example/ubuntu\n",
            "etc/apt/sources.list.d/c.sources": "URIs: https://ported.example:8443/ubuntu\n",
            "etc/apt/sources.list": "deb [arch=amd64] http://old.example/ubuntu noble main\n# deb http://no.example/ x\n",
        },
    )
    _, _, found = ask(root)
    assert found["reach_mirror.example"]["asked"] == "mirror.example:443"
    assert found["reach_plain.example"]["asked"] == "plain.example:80"
    assert found["reach_ported.example"]["asked"] == "ported.example:8443"
    assert found["reach_old.example"]["asked"] == "old.example:80"
    assert "reach_no.example" not in found


def test_only_sources_the_machine_uses_are_asked_and_all_of_a_fields(tmp_path):
    root = machine(
        tmp_path,
        {
            "etc/apt/sources.list.d/a.list.save": "deb http://saved.example/ubuntu noble main\n",
            "etc/apt/sources.list.d/b.sources": (
                "Enabled: no\nURIs: http://off.example/ubuntu\n\n"
                "Types: deb\nURIs: http://first.example/ubuntu https://second.example/ubuntu\n"
            ),
        },
    )
    _, _, found = ask(root)
    assert "reach_saved.example" not in found and "reach_off.example" not in found
    assert found["reach_first.example"]["asked"] == "first.example:80"
    assert found["reach_second.example"]["asked"] == "second.example:443"


def test_a_source_at_an_ipv6_address_is_asked_on_its_port_and_a_broken_target_is_a_finding(tmp_path, monkeypatch):
    root = machine(tmp_path, {"etc/apt/sources.list.d/a.sources": "URIs: http://[2001:db8::1]/ubuntu\n"})
    assert ask(root)[2]["reach_[2001:db8::1]"]["asked"] == "[2001:db8::1]:80"
    module = load()

    def broken(_self, _target):
        raise ValueError

    monkeypatch.setattr(module.Machine, "reaches", broken)
    start = time.monotonic()
    answer = module.run(module.Machine(str(root), True), LIMITS, {})
    assert time.monotonic() - start < 5
    assert next(row for row in answer["findings"] if row["id"] == "reach_[2001:db8::1]")["found"] == "ValueError"


def test_the_address_is_the_default_interfaces_own():
    module = load()
    assert module.Machine("", False).route_address("lo") == "127.0.0.1"
    assert module.Machine("", False).route_address("nosuch0") is None


def test_every_place_the_roles_fetch_from_is_in_the_limits():
    wanted = {target.split(":")[0] for targets in LIMITS["reach"].values() for target in targets}
    wanted.add("docker.io")
    named = set()
    roles = ROLE.parents[1]
    for path in [*roles.glob("*/vars/main.yml"), *roles.glob("*/defaults/main.yml")]:
        named |= set(
            re.findall(r"(?:https://|docker://|^\s+)([a-z0-9-]+(?:\.[a-z0-9-]+)+)/[a-zA-Z]", path.read_text(), re.M)
        )
    assert named and named <= wanted, named - wanted


def test_a_pool_of_no_memory_fails_its_shape(tmp_path):
    _, _, found = ask(machine(tmp_path), kvm=True, forge=True, pool={"systems": ["ubuntu"], "accounts": 1, "memory": 0})
    assert found["pool_shape"]["state"] == "fail"


def test_the_disk_is_reported_and_refuses_nothing_until_a_limit_is_measured(tmp_path):
    _, _, found = ask(machine(tmp_path))
    assert found["disk"]["state"] == "pass" and found["disk"]["found"] >= 0 and found["disk"]["unit"] == "GiB"


def test_a_setting_that_reads_as_words_fails(tmp_path):
    code, _, found = ask(machine(tmp_path), kvm="no")
    assert code == 1 and found["kvm_setting"]["state"] == "fail"


def test_what_systemd_cannot_say_is_unknown_and_not_passed(tmp_path):
    root = machine(tmp_path, {"delegated": None})
    _, _, found = ask(root)
    assert found["delegated"]["state"] == "unknown"


def test_it_writes_nothing_on_the_machine(tmp_path):
    root = machine(tmp_path)
    before = sorted((path, path.stat().st_mtime_ns) for path in root.rglob("*"))
    ask(root, kvm=True, forge=True, ports=[3001])
    assert sorted((path, path.stat().st_mtime_ns) for path in root.rglob("*")) == before


def test_limits_on_the_command_line_as_the_interface_sends_them_and_the_script_on_standard_input(tmp_path):
    done = subprocess.run(
        ["python3", "-", "--limits", json.dumps(LIMITS), "--root", str(machine(tmp_path)), "--no-network"],
        input=SCRIPT.read_text(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0 and json.loads(done.stdout)["ok"], done.stdout + done.stderr


def test_unreadable_limits_are_the_checks_own_failure(tmp_path):
    done = subprocess.run(
        ["python3", str(SCRIPT), "--limits", "not json", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 2 and json.loads(done.stdout)["complete"] is False


def load():
    """The script as a module, for what only a stand-in network can show."""
    loader = importlib.machinery.SourceFileLoader("porelo_host_check", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_a_target_that_does_not_answer_fails_and_names_it(tmp_path, monkeypatch):
    module = load()

    def refused(_self, _target):
        raise ConnectionRefusedError

    monkeypatch.setattr(module.Machine, "reaches", refused)
    answer = module.run(module.Machine(str(machine(tmp_path)), True), LIMITS, {"forge": False})
    row = next(row for row in answer["findings"] if row["id"] == "reach_fuinorg.jfrog.io")
    assert row["state"] == "fail" and row["found"] == "ConnectionRefusedError" and row["do"]


def test_a_stalled_resolver_cannot_hold_the_check_past_its_clock(tmp_path, monkeypatch):
    module = load()
    monkeypatch.setattr(module, "REACH_SECONDS", 1)

    def stalled(_self, _target):
        time.sleep(30)

    monkeypatch.setattr(module.Machine, "reaches", stalled)
    start = time.monotonic()
    answer = module.run(module.Machine(str(machine(tmp_path)), True), LIMITS, {"forge": True})
    assert time.monotonic() - start < 5
    row = next(row for row in answer["findings"] if row["id"] == "reach_codeberg.org")
    assert row["state"] == "fail" and row["found"] == "no answer in 1 s"


@pytest.mark.parametrize(
    "arguments",
    [
        ["--no-such-argument"],
        [
            "--limits",
            json.dumps({**LIMITS, "host_share_divisor": 0}),
            "--fit",
            json.dumps({"host_cpus": 4, "host_kib": 8}),
        ],
    ],
)
def test_what_goes_wrong_before_the_check_still_answers_one_object(arguments):
    done = subprocess.run(["python3", str(SCRIPT), *arguments], capture_output=True, text=True, check=False)
    assert done.returncode == 2, done.stderr
    assert json.loads(done.stdout)["complete"] is False


def hold_package_lock(root, seconds):
    """A package run as dpkg's lock shows it: another process holding the lock on the file."""
    lock = root / "var/lib/dpkg/lock-frontend"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.touch()
    holder = subprocess.Popen(
        [
            "python3",
            "-c",
            "import fcntl, sys, time\n"
            "f = open(sys.argv[1], 'r+')\n"
            "fcntl.lockf(f, fcntl.LOCK_EX)\n"
            "print('held', flush=True)\n"
            "time.sleep(float(sys.argv[2]))\n",
            str(lock),
            str(seconds),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert holder.stdout.readline().strip() == "held"
    return holder


def ask_waiting(root, wait):
    """The check as up asks it, over a machine whose other findings do not matter here."""
    done = subprocess.run(
        ["python3", str(SCRIPT), "--root", str(root), "--no-network", "--wait-packages", str(wait)],
        capture_output=True,
        text=True,
        check=False,
    )
    return next(row for row in json.loads(done.stdout)["findings"] if row["id"] == "packages_free")


def test_up_waits_out_a_package_run_that_ends(tmp_path):
    """Prevent up stopping at Ubuntu's daily package run, which nobody asked for and which ends by itself."""
    root = machine(tmp_path)
    holder = hold_package_lock(root, 3)
    try:
        start = time.monotonic()
        row = ask_waiting(root, 30)
    finally:
        holder.kill()
        holder.wait()
    assert row["state"] == "pass" and row["found"] == "free"
    assert 1 < time.monotonic() - start < 25


def test_up_stops_after_its_wait_on_a_package_run_that_does_not_end(tmp_path):
    root = machine(tmp_path)
    holder = hold_package_lock(root, 60)
    try:
        start = time.monotonic()
        row = ask_waiting(root, 1)
    finally:
        holder.kill()
        holder.wait()
    assert row["state"] == "fail" and row["found"] == "held" and row["do"]
    assert time.monotonic() - start < 5, "the wait is no longer than it says"


def test_the_interfaces_one_look_does_not_wait(tmp_path):
    root = machine(tmp_path)
    holder = hold_package_lock(root, 60)
    try:
        start = time.monotonic()
        row = ask_waiting(root, 0)
    finally:
        holder.kill()
        holder.wait()
    assert row["state"] == "fail" and row["found"] == "held"
    assert time.monotonic() - start < 5


def test_up_asks_the_check_to_wait():
    tasks = (Path(__file__).parents[3] / "roles/check/tasks/main.yml").read_text()
    assert "--wait-packages 300" in tasks


def test_a_run_starting_just_after_the_lock_was_free_does_not_say_held_without_a_wait(tmp_path, monkeypatch):
    """Prevent a second question to the kernel answering differently from the one the wait went by."""
    module = load()
    answers = iter([False, True])
    monkeypatch.setattr(module.Machine, "package_lock_held", lambda _self: next(answers))
    answer = module.run(module.Machine(str(machine(tmp_path)), False), LIMITS, {"forge": False}, wait_packages=300)
    row = next(row for row in answer["findings"] if row["id"] == "packages_free")
    assert row["found"] == "free"


def test_a_lock_that_cannot_be_asked_stays_one_finding_among_all_the_others(tmp_path, monkeypatch):
    """Prevent the wait taking every other finding from the interface, whose one look does not ask for a wait."""
    module = load()

    def broken(_self):
        raise OSError("no locks")

    monkeypatch.setattr(module.Machine, "package_lock_held", broken)
    monkeypatch.setattr(module.sys, "argv", [str(SCRIPT), "--root", str(machine(tmp_path)), "--no-network"])
    answer, code = module.answer_from_arguments()
    assert code == 1 and answer["complete"] is False
    assert {"cpus", "memory", "system"} <= {row["id"] for row in answer["findings"]}


def test_every_apt_of_up_waits_for_a_package_run_as_long_as_the_check():
    """Prevent a daily run starting after the check stopping up at apt's own 60 seconds."""
    import yaml

    plays = yaml.safe_load((Path(__file__).parents[3] / "playbooks/up.yml").read_text())
    assert all(play["module_defaults"]["ansible.builtin.apt"]["lock_timeout"] == 300 for play in plays)
