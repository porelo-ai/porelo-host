"""Guard destructive measurements, private output, and tables derived only from measured files."""

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

import pytest

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
