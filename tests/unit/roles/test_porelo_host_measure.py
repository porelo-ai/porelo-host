"""Guard destructive measurements, private output, and tables derived only from measured files."""

import importlib.machinery
import importlib.util
import hashlib
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[3]
SCRIPT = ROOT / "roles/measure/files/porelo-host-measure"
TABLES = ROOT / "build/measure-tables.py"
GIVEN = {"provider": "local", "offer": "small"}
SECRET = "planted-command-secret"


def load(path=SCRIPT):
    """Load a script without starting a measurement."""
    loader = importlib.machinery.SourceFileLoader(path.stem.replace("-", "_"), str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    # A cache beside a role's files would ship with it, and other tests read those files as text.
    writes = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = writes
    return module


# A fresh-word or membership guard bypass would let down delete somebody's data.
def test_without_the_fresh_word_nothing_is_changed(tmp_path):
    module = load()
    assert module.main(["--out", str(tmp_path / "out.json"), "--given", "{}"], module.Machine(tmp_path)) == 1
    assert list(tmp_path.iterdir()) == [], "a refusal must not even stage an inventory or result"


def prepare(root):
    """Only the files this script reads, without a network or real services."""
    files = {
        "etc/ssh/ssh_host_ed25519_key.pub": "ssh-ed25519 AAAA host\n",
        "etc/passwd": ("root:x:0:0:root:/root:/bin/bash\n" "person:x:1000:1000::/home/person:/bin/bash\n"),
        "etc/os-release": 'ID=ubuntu\nVERSION_ID="26.04"\n',
        "proc/cpuinfo": "processor : 0\nmodel name : Fixture CPU\nflags : vmx\nprocessor : 1\n",
        "proc/meminfo": "MemTotal: 4096000 kB\n",
        "proc/sys/kernel/osrelease": "fixture-kernel\n",
        "sys/block/vda/size": "8000\n",
        "sys/block/vda/queue/rotational": "0\n",
        "sys/fs/cgroup/system.slice/memory.current": "4096\n",
        "sys/fs/cgroup/system.slice/memory.peak": "8192\n",
        "sys/fs/cgroup/user.slice/memory.current": "2048\n",
        "sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/memory.current": "1024\n",
        "sys/fs/cgroup/user.slice/user-997.slice/memory.current": "512\n",
        "var/lib/dpkg/status": "Package: podman\nStatus: install ok installed\nVersion: 5.0\n\n",
    }
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    for name in ("home", "run", "var/cache", "etc/systemd/system", "usr/lib/systemd/user"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def standin(module, root, failure=False):
    """Use real fixture files; every external answer carries a secret that must be discarded."""

    class Standin(module.Machine):
        def __init__(self):
            super().__init__(root)
            self.calls = []
            self.tick = 0
            self.failure = failure

        def euid(self):
            return 0

        def pause(self, seconds):
            pass

        def clock(self):
            self.tick += 1
            return self.tick

        def command(self, arguments, timeout):
            assert arguments[:4] == ["ansible-playbook", "-c", "local", "-i"]
            inventory = json.loads(Path(arguments[4]).read_text())["all"]["hosts"]["localhost"]
            self.calls.append((arguments[-1], inventory))
            text = SECRET + "\n"
            if arguments[-1].endswith("up"):
                unit = self.path("/etc/systemd/system/new.service")
                unit.write_text("")
                status = self.path("/var/lib/dpkg/status")
                if "Package: porelo" not in status.read_text():
                    with status.open("a") as stream:
                        stream.write("Package: porelo\nStatus: install ok installed\nVersion: 1.0\n\n")
                    with self.path("/etc/passwd").open("a") as stream:
                        stream.write("porelo:x:1000:1000::/home/porelo:/bin/bash\n")
                        stream.write("porelo-forge:x:997:997::/home/porelo-forge:/bin/sh\n")
                    self.path("/home/porelo").mkdir()
                if self.failure and not inventory["porelo_host_forge"] and not inventory["porelo_host_room"]:
                    return 2, text + json.dumps(
                        {"v": 1, "state": "failed", "task": "Installing secrets " + SECRET, "msg": SECRET}
                    )
                return 2, text + json.dumps({"v": 1, "state": "waiting", "needs": [SECRET], "msg": SECRET})
            return 0, text + json.dumps({"v": 1, "state": "ok", "msg": SECRET, "task": SECRET})

    return Standin()


def measure(tmp_path, failure=False):
    module = load()
    machine = standin(module, prepare(tmp_path / "machine"), failure)
    out = tmp_path / "result.json"
    code = module.main(
        ["--fresh", "--out", str(out), "--given", '{"provider":"fixture","offer":"small"}', "--steps", "idle"], machine
    )
    return code, json.loads(out.read_text()) if out.exists() else None, machine, out


# Raw callback messages may contain keys; counts must not collapse independent observations.
def test_the_file_keeps_three_readings_and_no_command_secret(tmp_path):
    code, report, machine, out = measure(tmp_path)
    assert code == 0, "a completed file is success even with missing values"
    assert SECRET not in out.read_text(), "no external command's arbitrary text may enter the result"
    assert set(report) == {"v", "facts"} and report["v"] == 1
    assert len(machine.calls) == 24, "each of four shapes must have three separate up/down runs"
    for shape in ("none", "room", "forge", "both"):
        times = [r for r in report["facts"] if r["step"] == f"idle.{shape}" and r["field"] == "up.time"]
        assert [r["sample"] for r in times] == ["first", "second", "third"]
        assert all(r["value"] == 1 and r["unit"] == "seconds" for r in times)
    assert all("unit" in row and "step" in row for row in report["facts"])
    assert all(row.get("why") for row in report["facts"] if row["value"] is None)
    missing_peak = next(
        r for r in report["facts"] if r["field"] == "memory.peak" and r.get("subject") == "porelo-forge"
    )
    assert missing_peak["value"] is None and missing_peak["why"]
    current = {
        r["subject"]: r["value"] for r in report["facts"] if r["step"] == "idle.none" and r["field"] == "memory.current"
    }
    assert current["host"] == 4096 + 2048, "the host is the sum of the top slices, as the kernel's root has no file"
    assert current["porelo-forge"] == 512
    assert not any("1000" in r.get("subject", "") or "person" in r.get("subject", "") for r in report["facts"])
    agent = next(r for r in report["facts"] if r["step"] == "agent")
    assert "token" in agent["why"] and "varies" in agent["why"]


# A failed install must still clean up and cannot suppress measurements of other shapes.
def test_a_failed_up_is_null_and_the_next_shape_still_runs(tmp_path):
    code, report, machine, unused = measure(tmp_path, failure=True)
    assert code == 0
    failed = [r for r in report["facts"] if r["step"] == "idle.none" and r["field"] == "up.time"]
    assert len(failed) == 3 and all(r["value"] is None and r["why"] for r in failed)
    assert machine.calls[1][0] == "porelo.host.down"
    assert machine.calls[2][1]["porelo_host_room"] is True, "a failed shape must end rather than retry the same failure"
    assert any(r["step"] == "idle.room" and r["field"] == "up.time" and r["value"] == 1 for r in report["facts"])


# Residual installation needs to be visible before a disposable machine is returned.
def test_the_difference_names_new_packages_units_and_service_accounts(tmp_path):
    report = measure(tmp_path)[1]
    changes = {r["field"]: r["value"] for r in report["facts"] if r["field"].startswith("changes.")}
    assert changes["changes.packages.added"] == ["porelo"]
    assert changes["changes.units.added"] == ["new.service"]
    assert changes["changes.accounts.added"] == ["porelo", "porelo-forge"]
    assert changes["changes.directories.added"] == ["/home/porelo"]
    assert all(value == [] for field, value in changes.items() if field.endswith("removed"))


@pytest.mark.parametrize("obstruction", ["root", "person", "legacy-person", "room", "existing-result", "lock"])
def test_refusals_do_not_change_a_machine(tmp_path, obstruction):
    module = load()
    root = prepare(tmp_path / "machine")
    machine = standin(module, root)
    out = tmp_path / "result.json"
    if obstruction == "root":
        machine.euid = lambda: 1000
    elif obstruction in ("person", "legacy-person"):
        directory = "etc" if obstruction == "person" else "var/lib"
        path = root / directory / "porelo-host/people/person.conf"
        path.parent.mkdir(parents=True)
        path.write_text("member=host-admin\n")
    elif obstruction == "room":
        with (root / "etc/passwd").open("a") as stream:
            stream.write("porelo-matrix:x:1001:1001::/home/porelo-matrix:/bin/false\n")
    elif obstruction == "lock":
        (root / "run/porelo-host-measure.lock").write_text("leftover")
    else:
        out.write_text("previous measurement")
    before = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in tmp_path.rglob("*") if p.is_file()}
    code = module.main(["--fresh", "--out", str(out), "--given", "{}"], machine)
    assert code == 1
    assert {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in tmp_path.rglob("*") if p.is_file()} == before
    assert machine.calls == [], "even down would change a refused machine"


# Unknown fields and malformed numbers could bypass privacy rules or mislead capacity decisions.
def test_the_single_writer_refuses_fields_and_numbers_it_does_not_know():
    module = load()
    for field, value in (("secret", SECRET), ("memory.current", True), ("up.time", float("nan"))):
        with pytest.raises((KeyError, ValueError)):
            module.put({"facts": []}, field, value, "before")
    with pytest.raises(ValueError):
        module.put({"facts": []}, "memory.peak", None, "before")


# A changing host must not silently produce an idle measurement or wait forever.
def test_unsettled_memory_is_bounded_and_written_as_absent(tmp_path):
    module = load()
    machine = standin(module, prepare(tmp_path))
    n = 0

    def moving():
        nonlocal n
        n += 1
        return {"system.slice": {"current": n * 1024**3, "peak": n * 1024**3}}

    machine.groups = moving
    report = {"facts": []}
    module.readings(machine, report, "before", "first")
    assert n == 13 and all(r["value"] is None and "settle" in r["why"] for r in report["facts"])


# A cleanup failure leaves unknown state; no next up may compound the damage.
def test_a_failed_down_stops_without_publishing_a_partial_file(tmp_path):
    module = load()
    machine = standin(module, prepare(tmp_path / "machine"))
    command = machine.command

    def fail_down(arguments, timeout):
        if arguments[-1].endswith("down"):
            return 2, SECRET
        return command(arguments, timeout)

    machine.command = fail_down
    out = tmp_path / "out.json"
    assert module.main(["--fresh", "--out", str(out), "--given", "{}"], machine) == 2
    assert not out.exists() and len(machine.calls) == 1
    assert machine.path(
        "/run/porelo-host-measure.lock"
    ).exists(), "uncertain cleanup must block another destructive run"
    assert module.main(["--fresh", "--out", str(out), "--given", "{}"], machine) == 1
    assert len(machine.calls) == 1, "a retry must refuse the leftovers before another up"


# A known failed task is useful, but its message and unknown task text must stay private.
def test_only_a_known_stop_name_is_taken_from_the_lines():
    module = load()
    task = "Install safe packages"
    output = json.dumps({"v": 1, "state": "failed", "task": task, "msg": SECRET})
    assert module.outcome(2, output, {task}) == (None, task)
    assert module.outcome(2, output, set()) == (None, "unrecognized stop task")
    assert module.outcome(0, SECRET, {task})[0] is None


def test_up_guards_no_variable_nothing_sets():
    """Prevent a guard reading as protection, on a variable no role, playbook or script reads."""
    assert "porelo_host_person" not in (ROOT / "playbooks/up.yml").read_text()


def test_nothing_takes_a_run_past_the_capacity_check():
    """Prevent an allowance nothing uses staying as a way past the check, before a job step needs one."""
    for path in ("playbooks/up.yml", "playbooks/measure.yml", "roles/check/tasks/main.yml"):
        assert "measure_capacity" not in (ROOT / path).read_text()
    assert "measure_capacity" not in (ROOT / "roles/check/files/porelo-host-check").read_text()


# Publishing stale or fabricated tables can lead to an undersized rented machine.
def test_tables_name_the_source_and_nulls_and_reject_a_stale_page(tmp_path):
    module = load(TABLES)
    measures = tmp_path / "measures"
    measures.mkdir()
    fixture = Path(__file__).parent / "measure/result.json"
    (measures / "fixture.json").write_text(fixture.read_text())
    page = tmp_path / "machines.md"
    page.write_text("# Machines\n\n<!-- measures:start -->\n<!-- measures:end -->\n")
    assert module.main(["--check"], measures, page) == 1
    assert module.main([], measures, page) == 0
    assert "fixture" in page.read_text() and "not measured" in page.read_text()
    assert module.main(["--check"], measures, page) == 0
    report = json.loads((measures / "fixture.json").read_text())
    report["facts"].append({"field": "up.time", "value": 9, "unit": "seconds", "step": "idle.forge", "sample": "first"})
    (measures / "fixture.json").write_text(json.dumps(report))
    assert module.main(["--check"], measures, page) == 1


def test_a_shapes_row_shows_each_reading_in_use_and_with_the_cache_and_no_more_than_the_file_says(tmp_path):
    """Prevent a page giving a figure no run read, or the cache reading as what a host needs."""
    module = load(TABLES)
    mib = 1024**2

    def fact(field, value, step, sample=None, subject=None, unit="bytes", why=None):
        row = {"field": field, "value": value, "unit": unit, "step": step}
        row.update({key: item for key, item in (("sample", sample), ("subject", subject), ("why", why)) if item})
        return row

    facts = [
        fact("cpu.count", 4, "machine", unit="count"),
        fact("memory.total", 8192 * mib, "machine"),
        fact("provider", "local", "machine", unit="text"),
        fact("offer", "small", "machine", unit="text"),
        fact("up.time", 111.4, "idle.forge", "first", unit="seconds"),
        fact("memory.anon", 700 * mib, "idle.forge", "first", "host"),
        fact("memory.current", 2000 * mib, "idle.forge", "first", "host"),
        fact("memory.anon", 300 * mib, "idle.forge", "first", "porelo-forge"),
        fact("disk.used", 3 * 1024 * mib, "idle.forge", "first", "/"),
        fact("up.time", None, "idle.forge", "second", unit="seconds", why="a stop"),
        fact("work", None, "job", "first", unit="text", why="not measured"),
        fact("changes.accounts.added", ["porelo"], "after", unit="names"),
    ]
    (tmp_path / "small.json").write_text(json.dumps({"v": 1, "facts": facts}))
    page = module.tables(tmp_path)
    assert "### small" in page and "4 CPUs" in page and "8192 MiB" in page
    assert "| forge | first | 111 s | 700 MiB | 2000 MiB | 300 MiB | - | - | 3.0 GiB |" in page
    assert "| forge | second | not measured: a stop |" in page
    assert "porelo" in page and "job" in page


def test_the_machine_page_is_built_from_the_files():
    module = load(TABLES)
    assert module.main(["--check"]) == 0, "regenerate the machine page after changing a result file"


# A result with an unknown version must not be silently read as compatible measurements.
def test_tables_refuse_a_schema_they_do_not_know(tmp_path):
    module = load(TABLES)
    (tmp_path / "bad.json").write_text('{"v": 99, "facts": []}')
    with pytest.raises(ValueError):
        module.tables(tmp_path)


# A bad output path must be found before packages, services, or accounts can be changed.
def test_an_unusable_output_destination_prevents_all_up_down_calls(tmp_path):
    module = load()
    machine = standin(module, prepare(tmp_path / "machine"))
    assert module.main(["--fresh", "--out", str(tmp_path / "missing/result.json"), "--given", "{}"], machine) == 2
    assert machine.calls == [], "reserve the private result before starting destructive work"
    assert not machine.path("/run/porelo-host-measure.lock").exists()


# A termination must take the same cleanup path as Ctrl+C instead of leaving Ansible running detached.
def test_termination_is_an_interruption_and_down_runs_before_exit(tmp_path):
    import signal

    module = load()
    machine = standin(module, prepare(tmp_path / "machine"))
    command = machine.command
    calls = []

    def interrupted(arguments, timeout):
        calls.append(arguments[-1])
        if arguments[-1].endswith("up"):
            signal.raise_signal(signal.SIGTERM)
        return command(arguments, timeout)

    machine.command = interrupted
    out = tmp_path / "out.json"
    assert module.main(["--fresh", "--out", str(out), "--given", "{}"], machine) == 2
    assert calls == ["porelo.host.up", "porelo.host.down"]
    assert not out.exists() and not machine.path("/run/porelo-host-measure.lock").exists()


# A numeric hardware fact or file permission regression can invalidate an otherwise plausible report.
def test_the_machine_facts_and_private_file_permissions_come_from_the_fixture(tmp_path):
    code, report, unused, out = measure(tmp_path)
    machine = {r["field"]: r["value"] for r in report["facts"] if r["step"] == "machine"}
    assert code == 0
    assert machine["cpu.model"] == "Fixture CPU" and machine["cpu.count"] == 2
    assert machine["memory.total"] == 4096000 * 1024
    assert machine["disk.size"] == 8000 * 512 and machine["disk.rotational"] is False
    assert machine["cpu.virtualization"] == "vmx" and machine["kvm"] is False
    assert machine["system"] == "ubuntu 26.04" and machine["provider"] == "fixture"
    assert out.stat().st_mode & 0o777 == 0o600
    assert all(r["value"] is None and r.get("why") for r in report["facts"] if r["step"] in {"task", "agent", "job"})


# A timed-out Ansible child must not keep mutating the host while down starts.
def test_a_command_timeout_kills_its_whole_process_group(tmp_path, monkeypatch):
    import signal
    import subprocess

    module = load()
    calls = []

    class Child:
        pid = 123

        def __enter__(self):
            return self

        def __exit__(self, *arguments):
            return False

        def communicate(self, timeout=None):
            if timeout is not None:
                raise subprocess.TimeoutExpired("fixture-command", timeout)
            return SECRET, SECRET

    def spawn(arguments, **options):
        assert options["start_new_session"] is True
        assert options["env"]["ANSIBLE_STDOUT_CALLBACK"] == "porelo.host.lines"
        return Child()

    monkeypatch.setattr(module.subprocess, "Popen", spawn)
    monkeypatch.setattr(module.os, "killpg", lambda pid, sig: calls.append((pid, sig)))
    with pytest.raises(subprocess.TimeoutExpired):
        module.Machine(tmp_path).command(["fixture-command"], 1)
    assert calls == [(123, signal.SIGKILL)], "kill the group before cleanup can touch its state"


def test_an_up_is_given_a_stand_in_organization_that_nobody_can_sign(tmp_path):
    """Prevent the run stopping at a machine file only an interface hands over, or trusting a key someone holds."""
    code, report, machine, unused = measure(tmp_path)
    assert code == 0
    given = json.loads(machine.path("/etc/porelo-host/setup/machine.yml").read_text())["organization"]
    assert given["known_hosts"] == "central.example ssh-ed25519 AAAA\n"
    assert given["pin"].startswith("hostadmin ssh-ed25519 ") and "central.example" in given["settings"]
    assert machine.path("/etc/porelo-host/setup/machine.yml").stat().st_mode & 0o777 == 0o600
    assert {inventory["porelo_host_distribution"] for unused, inventory in machine.calls} == {"releases"}
    assert next(r for r in report["facts"] if r["field"] == "distribution")["value"] == "releases"


def test_memory_in_use_is_told_from_the_page_cache_and_new_service_accounts_are_named(tmp_path):
    """Prevent the kernel's cache reading as what a host needs, and a system account hiding what a run left."""
    root = prepare(tmp_path / "machine")
    (root / "sys/fs/cgroup/system.slice/memory.stat").write_text("anon 1024\nfile 3072\n")
    (root / "sys/fs/cgroup/user.slice/memory.stat").write_text("anon 512\nfile 0\n")
    module = load()
    machine = module.Machine(str(root))
    assert machine.groups()["host"]["anon"] == 1536
    assert machine.groups()["system.slice"]["anon"] == 1024
    before = machine.snapshot()
    with (root / "etc/passwd").open("a") as stream:
        stream.write("dnsmasq:x:120:120::/var/lib/misc:/bin/false\nsomeone:x:1001:1001::/home/someone:/bin/bash\n")
    report = {"v": 1, "facts": []}
    module.differences(report, before, machine.snapshot())
    added = next(r for r in report["facts"] if r["field"] == "changes.accounts.added")
    assert added["value"] == ["dnsmasq"] and "someone" not in json.dumps(report)


@pytest.mark.parametrize(
    "left",
    [
        "etc/porelo-host/organization/pin",
        "etc/porelo-host/projects/one",
        "etc/porelo-host/forge.conf",
        "etc/porelo-host/setup/machine.yml",
        "var/lib/porelo-host/pool/one",
        "etc/porelo-host/signers/one",
        "etc/porelo-host/host.json",
        "var/lib/porelo-host/arrivals/one",
    ],
)
def test_what_a_down_would_destroy_refuses_the_machine_unchanged(tmp_path, left):
    """Prevent --fresh destroying a host's organization, projects, forge or pool on a person's mistaken word."""
    module = load()
    machine = standin(module, prepare(tmp_path / "machine"))
    machine.path("/" + left).parent.mkdir(parents=True, exist_ok=True)
    machine.path("/" + left).write_text("kept")
    out = tmp_path / "result.json"
    arguments = ["--fresh", "--out", str(out), "--given", json.dumps(GIVEN)]
    assert module.main(arguments, machine) == 1
    assert machine.calls == [] and machine.path("/" + left).read_text() == "kept"


@pytest.mark.parametrize("account", ["porelo-forge", "porelo-runner"])
def test_a_forge_already_on_the_machine_refuses_it(tmp_path, account):
    """Prevent the repositories in a forge's volume going with the account a down removes."""
    module = load()
    root = prepare(tmp_path / "machine")
    text = "root:x:0:0:root:/root:/bin/bash\n" + f"{account}:x:997:997::/home/{account}:/bin/sh\n"
    (root / "etc/passwd").write_text(text)
    machine = standin(module, root)
    arguments = ["--fresh", "--out", str(tmp_path / "result.json"), "--given", json.dumps(GIVEN)]
    assert module.main(arguments, machine) == 1
    assert machine.calls == []


def test_another_run_is_a_refusal_and_touches_nothing(tmp_path):
    """Prevent a held lock reading as a failed run, or a stray file in the result's directory."""
    module = load()
    machine = standin(module, prepare(tmp_path / "machine"))
    machine.path("/run").mkdir(exist_ok=True)
    machine.path("/run/porelo-host-measure.lock").write_text("")
    directory = tmp_path / "out"
    directory.mkdir()
    arguments = ["--fresh", "--out", str(directory / "result.json"), "--given", json.dumps(GIVEN)]
    assert module.main(arguments, machine) == 1
    assert machine.calls == [] and list(directory.iterdir()) == []


def test_a_clean_down_after_an_interrupt_gives_the_lock_back_and_a_second_signal_cannot_stop_it(tmp_path):
    """Prevent a clean machine reading as leftovers, and a second signal cutting a down in two."""
    import signal

    module = load()
    machine = standin(module, prepare(tmp_path / "machine"))
    played = machine.command
    calls = []

    def interrupting(arguments, timeout):
        calls.append(arguments[-1])
        signal.raise_signal(signal.SIGTERM)
        signal.raise_signal(signal.SIGINT)
        return played(arguments, timeout)

    machine.command = interrupting
    arguments = ["--fresh", "--out", str(tmp_path / "result.json"), "--given", json.dumps(GIVEN)]
    assert module.main(arguments, machine) == 2
    assert calls == ["porelo.host.up", "porelo.host.down"], "the down runs whole, and nothing after it"
    assert not machine.path("/run/porelo-host-measure.lock").exists()


@pytest.mark.parametrize("name", ["SIGTERM", "SIGINT", "SIGHUP"])
def test_a_signal_during_a_cycles_down_stops_the_run_after_that_down(tmp_path, name):
    """Prevent a person's stop being lost when it lands in a down, or a dropped terminal leaving the lock and no down."""
    import signal

    module = load()
    machine = standin(module, prepare(tmp_path / "machine"))
    played = machine.command
    calls = []

    def signalled(arguments, timeout):
        calls.append(arguments[-1])
        if arguments[-1].endswith("down"):
            signal.raise_signal(getattr(signal, name))
        return played(arguments, timeout)

    machine.command = signalled
    arguments = ["--fresh", "--out", str(tmp_path / "result.json"), "--given", json.dumps(GIVEN)]
    assert module.main(arguments, machine) == 2
    assert calls == ["porelo.host.up", "porelo.host.down"], "no next up after the stop"
    assert not (tmp_path / "result.json").exists()
    assert not machine.path("/run/porelo-host-measure.lock").exists()


def test_the_handlers_are_given_back_after_a_run(tmp_path):
    """Prevent a run leaving its stop in a process that goes on."""
    import signal

    before = {n: signal.getsignal(n) for n in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    code, *unused = measure(tmp_path)
    assert code == 0
    assert {n: signal.getsignal(n) for n in before} == before


def test_a_failed_down_keeps_the_lock(tmp_path):
    """Prevent the next run measuring over what a failed down left."""
    module = load()
    machine = standin(module, prepare(tmp_path / "machine"))
    played = machine.command

    def failing(arguments, timeout):
        code, output = played(arguments, timeout)
        return (2, "failed") if arguments[-1].endswith("down") else (code, output)

    machine.command = failing
    arguments = ["--fresh", "--out", str(tmp_path / "result.json"), "--given", json.dumps(GIVEN)]
    assert module.main(arguments, machine) == 2
    assert machine.path("/run/porelo-host-measure.lock").exists()


def test_memory_moving_slowly_is_not_settled(tmp_path):
    """Prevent a machine still filling its memory reading as settled, each step being close to the last."""
    module = load()
    machine = standin(module, prepare(tmp_path / "machine"))
    grown = [1000 * 1024**2 + step * 9 * 1024**2 for step in range(40)]
    machine.groups = lambda: {"host": {"current": grown.pop(0), "anon": 0, "peak": None}}
    assert module.settled(machine) == "memory did not settle within 24 seconds"


def test_memory_in_use_moving_under_a_still_total_is_not_settled(tmp_path):
    """Prevent cache handed to a starting service hiding that it has not finished starting."""
    module = load()
    machine = standin(module, prepare(tmp_path / "machine"))
    grown = [100 * 1024**2 + step * 50 * 1024**2 for step in range(40)]
    machine.groups = lambda: {"host": {"current": 4096 * 1024**2, "anon": grown.pop(0), "peak": None}}
    assert module.settled(machine) == "memory did not settle within 24 seconds"


@pytest.mark.parametrize(
    "name,shown",
    [
        ("two.service", "two.service"),
        ("podman-kube@.service", "podman-kube@.service"),
        ("ssh@192.0.2.7.service", "ssh@.service"),
        ("one.service.1234.2026-11-05@00:00:00~", "one.service (backup)"),
        ("ssh@192.0.2.7.service~", "ssh@.service (backup)"),
        ("ssh@192.0.2.7.service.bak", "ssh@.service (backup)"),
        ("192.0.2.7.conf", "another file"),
        ("home-someone.mount", "another file"),
    ],
)
def test_a_unit_file_does_not_name_what_it_was_made_for(name, shown):
    """Prevent an instance's address, a mount's person or a backup's time reaching the result."""
    assert load().unit_name(name) == shown


def test_a_person_home_directory_stays_out_of_the_differences(tmp_path):
    """Prevent the difference naming a person by their home."""
    root = prepare(tmp_path / "machine")
    module = load()
    machine = module.Machine(str(root))
    before = machine.snapshot()
    (root / "home/someone").mkdir(parents=True)
    report = {"v": 1, "facts": []}
    module.differences(report, before, machine.snapshot())
    assert "someone" not in json.dumps(report)


def test_an_unusable_output_directory_leaves_no_lock_made(tmp_path, monkeypatch):
    """Prevent a run refused for its output touching /run at all."""
    module = load()
    machine = standin(module, prepare(tmp_path / "machine"))
    opened = []
    real = module.os.open
    monkeypatch.setattr(module.os, "open", lambda *a, **k: (opened.append(a[0]), real(*a, **k))[1])
    arguments = ["--fresh", "--out", str(tmp_path / "missing/result.json"), "--given", "{}"]
    assert module.main(arguments, machine) == 2
    assert not any("porelo-host-measure.lock" in str(path) for path in opened)


def test_the_summary_says_each_machines_range_by_shape_and_no_figure_a_reading_lacks(tmp_path):
    """Prevent the sizing table giving a number no reading holds, or hiding that a reading was not settled."""
    module = load(TABLES)
    mib = 1024**2

    def fact(field, value, step, sample=None, subject=None, why=None):
        row = {"field": field, "value": value, "unit": "bytes", "step": step}
        row.update({key: item for key, item in (("sample", sample), ("subject", subject), ("why", why)) if item})
        return row

    facts = [
        fact("memory.total", 4096 * mib, "machine"),
        fact("memory.anon", 300 * mib, "idle.room", "first", "host"),
        fact("memory.anon", 310 * mib, "idle.room", "second", "host"),
        fact("memory.anon", None, "idle.room", "third", "host", "memory did not settle"),
        fact("disk.used", 4 * 1024 * mib, "idle.room", "first", "/"),
        fact("disk.used", 4 * 1024 * mib, "idle.room", "second", "/"),
        fact("memory.anon", 500 * mib, "idle.forge", "first", "host"),
        fact("memory.anon", None, "idle.forge", "second", "host", "a stop"),
        fact("memory.anon", None, "idle.forge", "third", "host", "a stop"),
        fact("memory.anon", None, "idle.none", "first", "host", "the check refused"),
        fact("disk.used", None, "idle.none", "first", "/", "the check refused"),
    ]
    (tmp_path / "small.json").write_text(json.dumps({"v": 1, "facts": facts}))
    summary = module.summary(tmp_path)
    assert "| small | 4096 MiB | `room` | 300 to 310 MiB, 2 of 3 readings | 4.0 GiB, 2 of 3 readings |" in summary
    assert "| `forge` | 500 MiB, 1 of 3 readings |" in summary
    assert "| `none` | not measured: the check refused | not measured: the check refused |" in summary
    assert "| small | 4096 MiB | `both` | not measured | not measured |" in summary


def test_the_page_keeps_the_summary_built_and_refuses_it_stale(tmp_path):
    """Prevent the sizing table drifting from the files beside the full ones."""
    module = load(TABLES)
    assert module.SIZES_START in (ROOT / "doc/machines.md").read_text()
    measures = tmp_path / "measures"
    measures.mkdir()
    fixture = Path(__file__).parent / "measure/result.json"
    (measures / "fixture.json").write_text(fixture.read_text())
    page = tmp_path / "machines.md"
    page.write_text(f"{module.SIZES_START}\n{module.SIZES_END}\n<!-- measures:start -->\n<!-- measures:end -->\n")
    assert module.main([], measures, page) == 0
    assert "fixture" in page.read_text().split(module.SIZES_END)[0]
    assert module.main(["--check"], measures, page) == 0


STUB = b"\x7fELF stand-in stub agent"
STUB_PLACE = "https://fuinorg.jfrog.io/artifactory/porelo-dist-test/porelo-agent-stub/1.0/"


def developer_standin(module, root, refuse_start=False, digest=None, homeserver=True):
    """The idle stand-in, also answering the task step's commands as a host would, the developer's slice in files."""
    machine = standin(module, root)
    playbook = machine.command
    machine.fetched = []
    files = {
        STUB_PLACE + "porelo-agent-stub": STUB,
        STUB_PLACE + "porelo-agent-stub.sha256": ((digest or hashlib.sha256(STUB).hexdigest()) + "\n").encode(),
    }

    def fetch(url, timeout):
        machine.fetched.append(url)
        if url not in files:
            raise OSError("not found: " + url)
        return files[url]

    machine.fetch = fetch

    def command(arguments, timeout, given=None):
        if arguments[0] == "ansible-playbook":
            return playbook(arguments, timeout)
        machine.calls.append((arguments, given))
        words = arguments[arguments.index("--") + 1 :] if arguments[0] == "runuser" else arguments
        if words[0] == "useradd":
            with machine.path("/etc/passwd").open("a") as stream:
                stream.write("porelo-measure:x:1500:1500::/home/porelo-measure:/bin/bash\n")
            machine.path("/run/user/1500").mkdir(parents=True, exist_ok=True)
            machine.path("/run/user/1500/bus").write_text("")
            slice_ = machine.path("/sys/fs/cgroup/user.slice/user-1500.slice")
            slice_.mkdir(parents=True, exist_ok=True)
            (slice_ / "memory.current").write_text("3000\n")
            (slice_ / "memory.peak").write_text("9000\n")
            (slice_ / "memory.stat").write_text("anon 2000\nfile 1000\n")
            (slice_ / "cpu.stat").write_text("usage_usec 1000000\n")
        if words[0] == "userdel":
            passwd = machine.path("/etc/passwd")
            passwd.write_text(
                "".join(line for line in passwd.read_text().splitlines(True) if "porelo-measure" not in line)
            )
        if any("task start" in word for word in words):
            (machine.path("/sys/fs/cgroup/user.slice/user-1500.slice") / "cpu.stat").write_text("usage_usec 4500000\n")
            # The host records an uncertified start in test mode as it records every start, in root's task records,
            # under the project default.
            record = machine.path("/var/lib/porelo-host/tasks/porelo-measure/default")
            record.mkdir(parents=True, exist_ok=True)
            (record / "measure-1.json").write_text("{}")
            if refuse_start:
                return 1, "\x1b[31mstarting measure-1\x1b[0m\n\nporelo: the host refused (exit 65): no certificate\n"
        if words[-3:] == ["-p", "MemoryCurrent", "porelo-matrix-homeserver.service"]:
            return 0, "MemoryCurrent=123456\n" if homeserver else "MemoryCurrent=[not set]\n"
        return 0, SECRET

    machine.command = command
    return machine


def measure_tasks(tmp_path, refuse_start=False, digest=None, homeserver=True):
    module = load()
    machine = developer_standin(module, prepare(tmp_path / "machine"), refuse_start, digest, homeserver)
    out = tmp_path / "result.json"
    code = module.main(
        ["--fresh", "--out", str(out), "--given", "{}", "--steps", "task", "--tasks", "2"],
        machine,
    )
    return code, json.loads(out.read_text()) if out.exists() else None, machine, out


def others(machine):
    return [call for call in machine.calls if not isinstance(call[0], str)]


# The tasks' own cost, not an idle host's: a developer with a vault and a checkout, stub tasks started, and all of it gone.
def test_the_task_step_starts_a_throwaway_developers_stub_tasks_and_takes_them_away(tmp_path):
    code, report, machine, out = measure_tasks(tmp_path)
    assert code == 0
    assert SECRET not in out.read_text()
    rows = [r for r in report["facts"] if r["step"] == "task"]
    for sample in ("first", "second", "third"):
        mine = {(r["field"], r.get("subject")): r for r in rows if r.get("sample") == sample}
        assert mine[("start.time", "task 1")]["value"] > 0 and mine[("start.time", "task 2")]["value"] > 0
        assert mine[("memory.peak", "developer")]["value"] == 9000
        assert mine[("memory.anon", "developer")]["value"] == 2000
        assert mine[("cpu.time", "developer")]["value"] == pytest.approx(3.5)
        assert mine[("work", None)]["value"] == "2 stub tasks in default, one developer"
        assert mine[("work.time", None)]["value"] is None and "stub" in mine[("work.time", None)]["why"]
    calls = others(machine)
    vault = [given for arguments, given in calls if "vault" in arguments]
    assert len(vault) == 6 and all(given and given.endswith("\n") for given in vault), "init and unlock, per sample"
    assert not any(given.strip() in " ".join(arguments) for arguments, unused in calls for given in vault)
    starts = [arguments for arguments, unused in calls if arguments[-1].startswith("measure-")]
    assert [a[-1] for a in starts][:2] == ["measure-1", "measure-2"]
    assert any(arguments[:2] == ["userdel", "--remove"] for arguments, unused in calls)
    assert "porelo-measure" not in machine.path("/etc/passwd").read_text()
    plays = [call[0] for call in machine.calls if isinstance(call[0], str)]
    assert plays == ["porelo.host.up", "porelo.host.down"] * 3
    assert all(call[1]["porelo_host_room"] and not call[1]["porelo_host_forge"] for call in machine.calls[:1])
    assert not any(r["step"] == "task" and r["value"] is None and "not measured" in r.get("why", "") for r in rows)


def test_the_measuring_host_is_in_test_mode_and_its_starts_take_it_without_asking(tmp_path):
    """Prevent a measuring host starting no task for want of a certificate, or a host left in test mode unsaid."""
    code, unused_report, machine, unused_out = measure_tasks(tmp_path)
    assert code == 0
    ups = [call[1] for call in machine.calls if call[0] == "porelo.host.up"]
    assert ups and all(up["porelo_host_test_switches"] == ["start-uncertified"] for up in ups)
    assert not machine.path("/var/lib/porelo-host/tasks/porelo-measure").exists(), "the host's record of its starts"
    assert all("porelo-host-measure" in up["porelo_host_test_why"] for up in ups)
    starts = [" ".join(arguments) for arguments, unused in others(machine) if "task start" in " ".join(arguments)]
    assert starts and all(" --no-input --yes " in start for start in starts)


# A start that is refused must not leave a developer or its tasks, nor publish half a sample as whole.
def test_a_refused_task_start_is_null_with_its_reason_and_the_developer_is_still_removed(tmp_path):
    code, report, machine, unused = measure_tasks(tmp_path, refuse_start=True)
    assert code == 0
    rows = [r for r in report["facts"] if r["step"] == "task"]
    peaks = [r for r in rows if r["field"] == "memory.peak"]
    said = "task 1 of 2 did not start: starting measure-1 | porelo: the host refused (exit 65): no certificate"
    assert len(peaks) == 3 and all(r["value"] is None and r["why"] == said for r in peaks), "with its last words"
    starts = [arguments for arguments, unused in others(machine) if "task start" in " ".join(arguments)]
    assert starts and all("2>&1" in " ".join(arguments) for arguments in starts), "porelo says why on its errors"
    # As an idle shape that failed: the later samples are not tried again, and say why.
    assert sum(1 for arguments, unused in others(machine) if arguments[0] == "userdel") == 1
    assert "porelo-measure" not in machine.path("/etc/passwd").read_text()
    plays = [call[0] for call in machine.calls if isinstance(call[0], str)]
    assert plays.count("porelo.host.down") == 3


# The stub agent stays out of the package channels: it is fetched by the installed Porelo's version and its digest.
def test_the_stub_agent_comes_from_its_own_folder_by_porelos_version_and_digest(tmp_path):
    code, report, machine, unused = measure_tasks(tmp_path)
    assert code == 0
    assert machine.fetched[:2] == [STUB_PLACE + "porelo-agent-stub.sha256", STUB_PLACE + "porelo-agent-stub"]
    assert not any(arguments[0] == "apt-get" for arguments, unused in others(machine)), "no package channel is asked"
    starts = [i for i, (arguments, unused) in enumerate(others(machine)) if "measure-1" in arguments]
    placed = [i for i, (arguments, unused) in enumerate(others(machine)) if "install -D" in " ".join(arguments)]
    assert placed and placed[0] < starts[0], "the stub is in place before the first start"
    install = others(machine)[placed[0]][0]
    assert install[0] == "runuser", "the developer places it, so its home stays its own"
    assert install[-1] == "/home/porelo-measure/.local/lib/porelo-agent-stub/stub" and "755" in install
    registration = [given for arguments, given in others(machine) if "agents.d/stub.yaml" in " ".join(arguments)]
    assert registration == ["executable: /home/porelo-measure/.local/lib/porelo-agent-stub/stub\n"] * 3
    assert not machine.path("/run/porelo-host-measure-stub").exists(), "root's copy is gone once placed"


# A stub that is not the one its digest names must never run as the developer.
def test_a_stub_unlike_its_digest_is_null_with_its_reason_and_nothing_is_made(tmp_path):
    code, report, machine, unused = measure_tasks(tmp_path, digest="0" * 64)
    assert code == 0
    peaks = [r for r in report["facts"] if r["step"] == "task" and r["field"] == "memory.peak"]
    assert peaks and all(r["value"] is None and "SHA-256" in r["why"] for r in peaks)
    assert not any(
        arguments[0] == "useradd" or "install -D" in " ".join(arguments) for arguments, unused in others(machine)
    )


# The snapshots channel holds no release version, so a run from it names the newest snapshots it holds.
def test_a_run_from_the_snapshots_pins_the_newest_porelo_there(tmp_path):
    module = load()
    machine = developer_standin(module, prepare(tmp_path / "machine"))
    index = "Package: porelo\nVersion: 0.5.1~snapshot.508\n\nPackage: porelo-host\nVersion: 0.5.1~snapshot.508\n\n"
    index += "Package: porelo\nVersion: 0.5.1~snapshot.99\n\nPackage: porelo-agent-pi\nVersion: 0.5.1~snapshot.900\n\n"
    channel = "https://fuinorg.jfrog.io/artifactory/porelo-dist-deb/dists/snapshots/main/binary-amd64/Packages"
    fetch = machine.fetch
    machine.fetch = lambda url, timeout: index.encode() if url == channel else fetch(url, timeout)
    out = tmp_path / "result.json"
    arguments = ["--fresh", "--out", str(out), "--given", "{}", "--steps", "task", "--distribution", "snapshots"]
    assert module.main(arguments, machine) == 0
    inventory = machine.calls[0][1]
    assert inventory["porelo_host_distribution"] == "snapshots"
    assert inventory["porelo_version"] == "0.5.1~snapshot.508"
    assert inventory["porelo_host_version"] == "0.5.1~snapshot.508"


def job_standin(module, root, failing=()):
    """The idle stand-in, also answering the forge's API as a host's forge would; jobs end as asked."""
    machine = standin(module, root)
    playbook = machine.command
    machine.api = []
    machine.parts = []
    state = {"runs": 0, "commits": 0}

    def command(arguments, timeout, given=None):
        if arguments[0] == "ansible-playbook":
            code, output = playbook(arguments, timeout)
            if arguments[-1].endswith("up"):
                with machine.path("/etc/passwd").open("a") as stream:
                    stream.write("porelo-runner:x:996:996::/home/porelo-runner:/bin/sh\n")
                    stream.write("porelo-forge:x:995:995::/home/porelo-forge:/usr/sbin/nologin\n")
                runner = machine.path("/sys/fs/cgroup/user.slice/user-996.slice")
                runner.mkdir(parents=True, exist_ok=True)
                (runner / "memory.peak").write_text("7000\n")
                (runner / "cpu.stat").write_text("usage_usec 2000000\n")
                inventory = json.loads(Path(arguments[4]).read_text())["all"]["hosts"]["localhost"]
                if inventory.get("forge_runner_capacity") == 4 and "porelo_host_work_share" not in inventory:
                    return 2, json.dumps(
                        {
                            "v": 1,
                            "state": "failed",
                            "task": "forge : capacity | Stop when the runner's jobs and the VM pool would take more than the host's share for work",
                            "msg": SECRET,
                        }
                    )
                return 0, json.dumps({"v": 1, "state": "ok", "msg": SECRET})
            return code, output
        machine.calls.append((arguments, given))
        return 0, SECRET

    def forge(method, route, body=None):
        machine.api.append((method, route, body))
        if route.endswith("/contents/.forgejo/workflows/measure.yml"):
            state["commits"] += 1
            return 201, {"commit": {"sha": f"c{state['commits']}"}}
        if route.endswith("/actions/tasks"):
            # The runner takes one part a poll, so the rows grow; a run is done only when every part has one.
            sha = f"c{state['commits']}"
            state["polls"] = state.get("polls", 0) + 1 if state.get("sha") == sha else 1
            state["sha"] = sha
            failed = state["commits"] in failing
            rows = [
                {"id": 300 + part, "head_sha": sha, "status": "failure" if failed else "success"}
                for part in range(state["polls"])
            ]
            if failed:
                # The forge keeps each job's log in its data volume, as Forgejo writes it: a line a step, timed.
                logs = machine.path(f"/home/porelo-forge/{module.FORGE_DATA}/actions_log/{module.JOB_REPOSITORY}/2c")
                logs.mkdir(parents=True, exist_ok=True)
                (logs / "300.log").write_text(
                    "2026-11-13T05:36:01.0000000Z Run ./mvnw\n"
                    "2026-11-13T05:36:09.0000000Z \x1b[31m[ERROR]\x1b[0m Failed to execute goal on project release\n"
                    "2026-11-13T05:36:09.5000000Z \n"
                    "2026-11-13T05:36:10.0000000Z ::error::Process completed with exit code 1.\n"
                )
            machine.parts.append(len(rows))
            return 200, {"workflow_runs": rows}
        if "/contents/" in route and method == "GET":
            return 200, {"sha": "blob"}
        if route.endswith("/branches"):
            return 201, {"commit": {"id": module.JOB_TREE}}
        return {"POST": 201, "DELETE": 204}.get(method, 200), {}

    machine.command = command
    machine.forge = forge
    return machine


def measure_jobs(tmp_path, failing=()):
    module = load()
    machine = job_standin(module, prepare(tmp_path / "machine"), failing)
    out = tmp_path / "result.json"
    code = module.main(["--fresh", "--out", str(out), "--given", "{}", "--steps", "job"], machine)
    return code, json.loads(out.read_text()) if out.exists() else None, machine, module


# A job's cost on the host's own forge: buildtools built at 1, 2 and 4 jobs and past the half, cold and with the cache.
def test_the_job_step_builds_the_pinned_tree_cold_and_cached_at_each_count(tmp_path):
    code, report, machine, module = measure_jobs(tmp_path)
    assert code == 0
    rows = {(r["field"], r.get("subject")): r for r in report["facts"] if r["step"] == "job"}
    for label in ("1 job", "2 jobs", "4 jobs past the half"):
        for run in ("cold", "with the cache"):
            assert rows[("work.time", f"{label}, {run}")]["value"] > 0
        assert rows[("memory.peak", f"{label}, cold")]["value"] == 7000
        cached = rows[("memory.peak", f"{label}, with the cache")]
        assert cached["value"] is None and "cold run" in cached["why"]
    refused = rows[("work.time", "4 jobs, cold")]
    assert refused["value"] is None and "share for work" in refused["why"]
    ups = [inventory for name, inventory in machine.calls if isinstance(name, str) and name.endswith("up")]
    assert [u.get("forge_runner_capacity") for u in ups] == [1, 2, 4, 4]
    assert [u.get("porelo_host_work_share") for u in ups] == [None, None, None, 90]
    assert all(u["porelo_host_forge"] and not u["porelo_host_room"] for u in ups)
    plays = [name for name, unused in machine.calls if isinstance(name, str)]
    assert plays == ["porelo.host.up", "porelo.host.down"] * 4
    migrations = [body for method, route, body in machine.api if route == "repos/migrate"]
    assert len(migrations) == 3 and all(b["clone_addr"] == module.JOB_SOURCE for b in migrations)
    branches = [body for method, route, body in machine.api if route.endswith("/branches")]
    assert all(b["old_ref_name"] == module.JOB_TAG for b in branches)
    workflows = [body for method, route, body in machine.api if route.endswith("measure.yml")]
    assert len(workflows) == 6
    assert [body.get("sha") for body in workflows] == [None, "blob"] * 3, "the cached run changes the cold run's file"
    assert max(machine.parts) == 4 and 3 in machine.parts, "a 4-job run waited past its third part"
    deleted = [route for method, route, unused in machine.api if method == "DELETE"]
    assert len(deleted) == 3, "the repository goes after each count's runs"
    rows_agent = [r for r in report["facts"] if r["step"] == "agent"]
    assert rows_agent and all(r["value"] is None for r in rows_agent)
    assert not any(r["step"] == "job" and "not measured" in r.get("why", "") for r in report["facts"])


# The workflow each count commits is one YAML document: N parts of one build, the count's own cache key.
def test_the_job_workflow_runs_n_parts_of_the_pinned_build_with_the_counts_own_cache():
    module = load()
    workflow = yaml.safe_load(module.job_workflow(4, "4 jobs past the half", "cold"))
    build = workflow["jobs"]["build"]
    assert build["strategy"]["matrix"]["part"] == [1, 2, 3, 4]
    assert build["steps"][0]["with"]["key"] == "measure-4-jobs-past-the-half"
    assert "./mvnw -B -s settings.xml -DskipTests package" in build["steps"][1]["run"]
    assert (
        "Authorization: token" in build["steps"][1]["run"] and "github.token" in build["steps"][1]["env"]["FORGE_TOKEN"]
    )


# The forge's admin token is read by root and goes to curl on standard input, never onto a command line.
def test_the_forge_is_asked_with_its_token_on_standard_input_only(tmp_path):
    module = load()
    root = prepare(tmp_path / "machine")
    with (root / "etc/passwd").open("a") as stream:
        stream.write("porelo-forge:x:997:997::/var/lib/porelo-forge:/bin/sh\n")
    token = root / "var/lib/porelo-forge/.config/porelo-forge/api.token"
    token.parent.mkdir(parents=True)
    token.write_text(SECRET + "\n")
    machine = module.Machine(root)
    asked = []
    machine.command = lambda arguments, timeout, given=None: asked.append((arguments, given)) or (0, '{"a": 1}\n201')
    assert machine.forge("POST", "repos/migrate", {"x": 1}) == (201, {"a": 1})
    arguments, given = asked[0]
    assert SECRET not in " ".join(arguments) and SECRET in given
    assert "/run/user/997/porelo-forge/http.sock" in arguments


# A failed build is not a time: null with its reason, and the host still goes down clean.
def test_a_failed_job_is_null_with_its_reason_and_the_repository_still_goes(tmp_path):
    code, report, machine, module = measure_jobs(tmp_path, failing=(1,))
    assert code == 0
    first = [r for r in report["facts"] if r["step"] == "job" and r.get("subject") == "1 job, cold"]
    assert first and all(r["value"] is None and "failure" in r["why"] for r in first)
    # The tail of the failed job's own log, its last lines without times or colours, so a reader knows which step.
    assert all(
        r["why"].endswith(
            ": [ERROR] Failed to execute goal on project release | ::error::Process completed with exit code 1."
        )
        for r in first
    ), first[0]["why"]
    deleted = [route for method, route, unused in machine.api if method == "DELETE"]
    assert len(deleted) == 3


def raise_standin(module, root, pressure_from=None, refuse_from=None, psi=True, stuck=None):
    """The task stand-in with many developers: each account its own uid and bus; pressure and refusals by count."""
    machine = developer_standin(module, root)
    inner = machine.command
    machine.accounts = []
    # The inherited start answer writes the one developer's slice; here it only has to exist.
    machine.path("/sys/fs/cgroup/user.slice/user-1500.slice").mkdir(parents=True, exist_ok=True)

    def command(arguments, timeout, given=None):
        if arguments[0] == "useradd":
            name = arguments[-1]
            machine.calls.append((arguments, given))
            uid = 1600 + len(machine.accounts)
            machine.accounts.append(name)
            with machine.path("/etc/passwd").open("a") as stream:
                stream.write(f"{name}:x:{uid}:{uid}::/home/{name}:/bin/bash\n")
            machine.path(f"/run/user/{uid}").mkdir(parents=True, exist_ok=True)
            machine.path(f"/run/user/{uid}/bus").write_text("")
            live = len([a for a in machine.accounts if a.startswith("porelo-measure-")])
            level = "42.00" if pressure_from and live >= pressure_from else "0.00"
            if psi:
                machine.path("/proc/pressure").mkdir(parents=True, exist_ok=True)
                memory = f"some avg10={level} avg60=0.00 avg300=0.00 total=1\n"
                machine.path("/proc/pressure/memory").write_text(memory)
                machine.path("/proc/pressure/cpu").write_text("some avg10=0.00 avg60=0.00 avg300=0.00 total=1\n")
            return 0, SECRET
        if arguments[0] == "userdel":
            machine.calls.append((arguments, given))
            name = arguments[-1]
            if name == stuck:
                return 8, SECRET
            passwd = machine.path("/etc/passwd")
            passwd.write_text(
                "".join(line for line in passwd.read_text().splitlines(True) if not line.startswith(name + ":"))
            )
            return 0, SECRET
        if arguments[0] == "runuser" and any("task start" in word for word in arguments):
            name = arguments[2]
            if refuse_from and name.startswith("porelo-measure-") and int(name.rsplit("-", 1)[1]) >= refuse_from:
                machine.calls.append((arguments, given))
                return 1, "porelo: the host refused (exit 65): no certificate\n"
        return inner(arguments, timeout, given)

    machine.command = command
    return machine


def measure_raise(tmp_path, **settings):
    module = load()
    machine = raise_standin(module, prepare(tmp_path / "machine"), **settings)
    out = tmp_path / "result.json"
    code = module.main(["--fresh", "--out", str(out), "--given", "{}", "--steps", "task", "--raise"], machine)
    return code, json.loads(out.read_text()) if out.exists() else None, machine


def raised(report):
    return {r["field"]: r for r in report["facts"] if r["step"] == "task" and r.get("subject") == "raised"}


# How many developers a host holds: raised 1, 2, 4 and on, five tasks each, until the memory's pressure stays high.
def test_developers_are_raised_until_the_pressure_stays_high_and_all_go_again(tmp_path):
    code, report, machine = measure_raise(tmp_path, pressure_from=4)
    assert code == 0
    rows = raised(report)
    assert rows["developers"]["value"] == 2
    assert "memory pressure" in rows["work"]["value"]
    made = [a for a in machine.accounts if a.startswith("porelo-measure-")]
    assert made == [f"porelo-measure-{n}" for n in range(1, 5)], "the level that suffered was made in full"
    starts = [a for a, unused in others(machine) if a[0] == "runuser" and a[2].startswith("porelo-measure-")
              and any("task start" in w for w in a)]  # fmt: skip
    assert len(starts) == 4 * 5, "five tasks each"
    stopped = [
        a[2]
        for a, unused in others(machine)
        if a[0] == "runuser" and a[-2:] == ["stop", "porelo-matrix-homeserver.service"]
    ]
    assert [s for s in stopped if s.startswith("porelo-measure-")] == made, "each one's own homeserver taken out"
    assert not any(line.startswith("porelo-measure") for line in machine.path("/etc/passwd").read_text().splitlines())
    plays = [name for name, unused in machine.calls if isinstance(name, str)]
    assert plays == ["porelo.host.up", "porelo.host.down"] * 4, "three samples and the raising, each its own up"


# A start that fails ends the raising there: the count before it is what the host held.
def test_a_refused_start_ends_the_raising_at_the_level_before(tmp_path):
    code, report, machine = measure_raise(tmp_path, refuse_from=3)
    assert code == 0
    rows = raised(report)
    assert rows["developers"]["value"] == 2
    assert rows["work"]["value"].endswith("did not start: porelo: the host refused (exit 65): no certificate")
    assert not any(line.startswith("porelo-measure") for line in machine.path("/etc/passwd").read_text().splitlines())


# Without the word, no raising: the task step stays three samples of one developer.
def test_without_raise_the_task_step_is_three_samples(tmp_path):
    code, report, machine, unused = measure_tasks(tmp_path)
    assert not raised(report)


# A kernel that tells no pressure cannot say a level held: the raising stops and says so.
def test_without_the_kernels_pressure_no_level_is_said_to_hold(tmp_path):
    code, report, machine = measure_raise(tmp_path, psi=False)
    assert code == 0
    rows = raised(report)
    assert rows["developers"]["value"] is None and "no memory pressure" in rows["developers"]["why"]


# A host that holds every level says so, with the last level's count.
def test_a_host_that_holds_every_level_names_the_last(tmp_path):
    code, report, machine = measure_raise(tmp_path)
    assert code == 0
    rows = raised(report)
    assert rows["developers"]["value"] == 32 and "the last level, 32 developers, held" in rows["work"]["value"]
    assert not any(line.startswith("porelo-measure") for line in machine.path("/etc/passwd").read_text().splitlines())


# One developer that will not go must not keep the others or the down from running; the run then ends without a file.
def test_a_developer_that_stays_still_lets_the_others_go_and_the_host_down(tmp_path):
    code, report, machine = measure_raise(tmp_path, pressure_from=4, stuck="porelo-measure-2")
    assert code == 2 and report is None
    names = [line.split(":")[0] for line in machine.path("/etc/passwd").read_text().splitlines()]
    assert "porelo-measure-2" in names and not {"porelo-measure-1", "porelo-measure-3", "porelo-measure-4"} & set(names)
    plays = [name for name, unused in machine.calls if isinstance(name, str)]
    assert plays[-1] == "porelo.host.down"


# Raising belongs to the task step; asked for alone it is refused before anything is touched.
def test_raise_without_the_task_step_is_refused(tmp_path):
    module = load()
    machine = raise_standin(module, prepare(tmp_path / "machine"))
    with pytest.raises(SystemExit):
        module.main(
            ["--fresh", "--out", str(tmp_path / "r.json"), "--given", "{}", "--steps", "idle", "--raise"], machine
        )
    assert not machine.calls


def words_of(arguments):
    return arguments[arguments.index("--") + 1 :] if arguments[0] == "runuser" else arguments


# Each developer's own homeserver stands in for the host's one gate: read as its own, then taken out of the reading.
def test_each_developers_own_homeserver_is_read_and_stopped_before_its_slice(tmp_path):
    code, report, machine, unused = measure_tasks(tmp_path)
    assert code == 0
    rows = [r for r in report["facts"] if r["step"] == "task" and r.get("subject") == "developer's own homeserver"]
    assert len(rows) == 3 and all(r["field"] == "memory.current" and r["value"] == 123456 for r in rows)
    calls = [words_of(a) for a, unused in others(machine)]
    stops = [i for i, w in enumerate(calls) if w[-2:] == ["stop", "porelo-matrix-homeserver.service"]]
    starts = [i for i, w in enumerate(calls) if any("task start" in word for word in w)]
    assert len(stops) == 3 and all(any(s < stop for s in starts) for stop in stops)
    assert all(calls[i][-4:-2] == ["systemctl", "--user"] and calls[i][0] == "env" for i in stops), "as the developer"


# An account whose homeserver never ran says so, and its reading is the developer's alone.
def test_a_developer_without_its_own_homeserver_says_so(tmp_path):
    code, report, machine, unused = measure_tasks(tmp_path, homeserver=False)
    assert code == 0
    rows = [r for r in report["facts"] if r.get("subject") == "developer's own homeserver"]
    assert rows and all(r["value"] is None and "no homeserver of its own" in r["why"] for r in rows)


def handed_over(machine, stub=True):
    """Packages as build/stage-packages.sh stages them: <package>.deb and .version, and SHA256SUMS over all of them."""
    directory = machine.path("/root/measure-packages")
    directory.mkdir(parents=True)
    names = ["porelo", "porelo-host"] + (["porelo-agent-stub"] if stub else [])
    for name in names:
        (directory / f"{name}.deb").write_bytes(f"deb of {name}".encode())
        (directory / f"{name}.version").write_text("0.5.1~snapshot.20261113T172922+local.20261113T172922\n")
    sums = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  ./{path.name}\n" for path in sorted(directory.iterdir())
    )
    (directory / "SHA256SUMS").write_text(sums)
    return directory


# A local hand-over is installed as checked as the channel is: by its sums, its versions pinned, its own stub taken.
def test_a_run_from_handed_over_packages_installs_them_by_their_sums_and_takes_their_stub(tmp_path):
    module = load()
    machine = developer_standin(module, prepare(tmp_path / "machine"))
    handed_over(machine)
    out = tmp_path / "result.json"
    arguments = [
        "--fresh",
        "--out",
        str(out),
        "--given",
        "{}",
        "--steps",
        "task",
        "--packages",
        "/root/measure-packages",
    ]
    assert module.main(arguments, machine) == 0
    inventory = machine.calls[0][1]
    assert inventory["porelo_local_packages"] == "/root/measure-packages"
    assert inventory["porelo_version"] == "0.5.1~snapshot.20261113T172922+local.20261113T172922"
    assert inventory["porelo_host_version"] == inventory["porelo_version"]
    assert not machine.fetched, "the stub comes with the packages, not from the stub folder"
    assert not any("install -D" in " ".join(arguments) for arguments, unused in others(machine))
    report = json.loads(out.read_text())
    assert any(r["field"] == "packages" and len(r["value"]) == 64 for r in report["facts"])


# A package changed after its sum was taken must never reach the host.
def test_a_handed_over_package_that_does_not_match_its_sum_is_refused_before_any_up(tmp_path):
    module = load()
    machine = developer_standin(module, prepare(tmp_path / "machine"))
    directory = handed_over(machine)
    (directory / "porelo.deb").write_bytes(b"something else")
    out = tmp_path / "result.json"
    arguments = [
        "--fresh",
        "--out",
        str(out),
        "--given",
        "{}",
        "--steps",
        "task",
        "--packages",
        "/root/measure-packages",
    ]
    assert module.main(arguments, machine) != 0
    assert not machine.calls, "nothing was played"
    assert not out.exists()
