"""Guard the move's read-only check and the room's tunnel against saying more than they saw."""

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "build/move-check.sh"
TUNNEL = ROOT / "build/room-tunnel.sh"

GOOD = {
    "status": json.dumps({"name": "t1", "running": True, "project": "porelo", "repository": "sluice"}),
    "status_text": "task       t1\nforge      porelo/t1\npull req   http://forge/pulls/7\n",
    "build": json.dumps({"branch": "porelo/t1", "commit": "a" * 40, "verdict": "success"}),
    "peers": "Agent Sluice\nAgent Core\n",
}


def fake(path, name, body):
    command = path / name
    command.write_text("#!/bin/sh\n" + body)
    command.chmod(0o755)


@pytest.fixture
def porelo(tmp_path):
    """A stand-in for Porelo, recording each call, so that a write would show."""

    def install(**answers):
        values = {**GOOD, **answers}
        log = tmp_path / "calls"
        for key, value in values.items():
            (tmp_path / key).write_text(value)
        fake(
            tmp_path,
            "porelo",
            f"""echo "$*" >> {log}
case "$1 $2 $*" in
    "task status "*--json*) cat {tmp_path}/status ;;
    "task status "*) cat {tmp_path}/status_text ;;
    "build status "*) cat {tmp_path}/build ;;
    "talk peers "*) cat {tmp_path}/peers ;;
    *) echo "unexpected: $*" >&2; exit 99 ;;
esac
""",
        )
        return log

    return install


def check(tmp_path, *arguments):
    environment = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"}
    return subprocess.run([str(CHECK), *arguments], capture_output=True, text=True, env=environment, check=False)


def test_every_line_holds_once_the_agent_has_moved(tmp_path, porelo):
    """Prevent the check staying red after a move that went right."""
    calls = porelo()
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.count("ok:") == 6 and "FAILED" not in done.stdout
    assert all(line.split()[0] in ("task", "build", "talk") for line in calls.read_text().splitlines())
    assert "--logs=none" in calls.read_text() and "--branch=porelo/t1" in calls.read_text()


@pytest.mark.parametrize(
    "answers, named",
    [
        (dict(status=json.dumps({"name": "t1", "state": "absent", "running": False})), "the task runs"),
        (dict(build=json.dumps({"branch": "porelo/t1", "commit": None, "verdict": "unknown"})), "last push"),
        (dict(build=json.dumps({"branch": "porelo/t1", "commit": "a" * 40, "verdict": "unknown"})), "Build"),
        (dict(status_text="task       t1\n"), "pull request"),
        (dict(peers="Agent Core\n"), "agent-card"),
    ],
)
def test_each_line_fails_by_name(tmp_path, porelo, answers, named):
    """Prevent a move passing with one of the procedure's facts missing, or a failure naming nothing."""
    porelo(**answers)
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 1
    assert any(line.startswith("FAILED") and named in line for line in done.stdout.splitlines()), done.stdout


def test_the_wake_counts_only_when_the_person_who_posted_says_so(tmp_path, porelo):
    """Prevent a read-only check claiming an answer it cannot have seen."""
    porelo()
    done = check(tmp_path, "t1", "Agent Sluice")
    assert done.returncode == 1
    assert "FAILED" in done.stdout and "wakes it" in done.stdout


def test_reading_a_failed_build_holds_this_line_as_the_moves_own_work_judges_the_verdict(tmp_path, porelo):
    """Prevent reading the Build being confused with the Build passing, which the move's own work judges."""
    porelo(build=json.dumps({"branch": "porelo/t1", "commit": "a" * 40, "verdict": "failure"}))
    assert check(tmp_path, "t1", "Agent Sluice", "--wake-answered").returncode == 0


def test_missing_arguments_are_refused(tmp_path, porelo):
    porelo()
    assert check(tmp_path).returncode == 64


def run_tunnel(tmp_path, *arguments):
    log = tmp_path / "ssh-calls"
    fake(tmp_path, "ssh", f'echo "$*" >> {log}\nexit 0\n')
    environment = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "ROOM_TUNNEL_ONCE": "1"}
    done = subprocess.run([str(TUNNEL), *arguments], capture_output=True, text=True, env=environment, check=False)
    return done, log.read_text() if log.exists() else ""


def test_the_tunnel_binds_one_socket_of_the_persons_own_to_the_homeservers_port(tmp_path):
    """Prevent the tunnel taking the window's return socket, a TCP listener, or a shell on the host."""
    done, calls = run_tunnel(tmp_path, "alice", "host.example", "8448")
    assert done.returncode == 0, done.stderr
    assert "-R /run/porelo-host/people/alice/room.sock:127.0.0.1:8448" in calls
    assert " -N " in f" {calls} " and "ExitOnForwardFailure=yes" in calls and "StreamLocalBindUnlink=yes" in calls
    assert "return.sock" not in calls and calls.rstrip().endswith("alice@host.example")
    assert done.stdout.strip() == "unix:/run/porelo-host/people/alice/room.sock"


@pytest.mark.parametrize(
    "arguments",
    [
        ("alice\nbad x", "room.example", "8448"),
        ("alice", "room.example\nbad x", "8448"),
        ("alice", "room.example", "8448\nx"),
    ],
)
def test_the_tunnel_refuses_a_value_with_a_second_line(tmp_path, arguments):
    """Prevent grep passing a value because one of its lines fits, the rest reaching ssh."""
    done, calls = run_tunnel(tmp_path, *arguments)
    assert done.returncode == 64 and not calls


@pytest.mark.parametrize(
    "arguments",
    [
        ("alice", "host.example"),
        ("Al/ice", "host.example", "8448"),
        ("alice", "-oProxyCommand=x", "8448"),
        ("alice", "host.example", "port"),
        ("alice", "host.example", "70000"),
    ],
)
def test_the_tunnel_refuses_what_could_become_an_option_or_a_path(tmp_path, arguments):
    """Prevent an argument turning into an ssh option or leaving the person's directory."""
    done, calls = run_tunnel(tmp_path, *arguments)
    assert done.returncode == 64 and not calls


REHEARSE = ROOT / "build/rehearse-move.sh"


def rehearsal(tmp_path, *, listed="", running=False):
    """The rehearsal script in a checkout of its own, with virsh and porelo-vm stood in for, each call recorded."""
    root = tmp_path / "checkout"
    (root / "build").mkdir(parents=True)
    (root / "roles/vm_pool/files").mkdir(parents=True)
    script = root / "build/rehearse-move.sh"
    script.write_bytes(REHEARSE.read_bytes())
    script.chmod(0o755)
    (root / "build/test-image").write_bytes((ROOT / "build/test-image").read_bytes())
    tunnel = root / "build/room-tunnel.sh"
    tunnel.write_bytes(TUNNEL.read_bytes())
    tunnel.chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls"
    (tmp_path / "listed").write_text(listed)
    fake(
        bin_dir,
        "virsh",
        f"""echo "virsh $*" >> {log}
case "$1" in
    list) cat {tmp_path / "listed"} ;;
    vol-list) printf ' Name Path\\n----\\n' ;;
    domstate) {"echo running" if running else "echo 'shut off'"} ;;
esac
""",
    )
    fake(root / "roles/vm_pool/files", "porelo-vm", f'echo "porelo-vm $*" >> {log}\n')
    fake(bin_dir, "ssh", f'echo "ssh $*" >> {log}\n')
    fake(bin_dir, "curl", f'echo "curl $*" >> {log}\nexit 22\n')

    def call(*arguments):
        environment = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path)}
        done = subprocess.run([str(script), *arguments], capture_output=True, text=True, env=environment, check=False)
        return done, log.read_text() if log.exists() else ""

    return root / "target/rehearsal", call


def test_a_start_over_an_earlier_rehearsals_vm_is_refused_and_names_it(tmp_path):
    """Prevent a rehearsal taking over, or later deleting, a VM another run left."""
    state, call = rehearsal(tmp_path, listed="porelo-host-rehearsal-20261106t120000z\n")
    done, calls = call("start")
    assert done.returncode != 0, "a start over a left VM must fail"
    assert "porelo-host-rehearsal-20261106t120000z" in done.stderr, "the refusal names what was left"
    assert "porelo-vm" not in calls and "curl" not in calls, "nothing is fetched or made after the refusal"
    assert not state.exists(), "no run's directory is made"


def test_down_deletes_only_the_vm_its_own_run_made(tmp_path):
    """Prevent down deleting a VM by any name but the one its start recorded."""
    state, call = rehearsal(tmp_path)
    state.mkdir(parents=True)
    (state / "name").write_text("porelo-host-rehearsal-20261106t150000z\n")
    (state / "organization").write_text("\n")
    done, calls = call("down")
    assert done.returncode == 0, done.stderr
    deleted = [line for line in calls.splitlines() if line.startswith("porelo-vm delete")]
    assert deleted == ["porelo-vm delete porelo-host-rehearsal-20261106t150000z"], "only the run's own VM is deleted"
    assert not state.exists(), "the run's directory goes with it"


def test_down_refuses_a_recorded_name_that_is_no_rehearsals(tmp_path):
    """Prevent a changed record making down delete another VM on the machine."""
    state, call = rehearsal(tmp_path)
    state.mkdir(parents=True)
    (state / "name").write_text("ubuntu26.04\n")
    done, calls = call("down")
    assert done.returncode != 0, "a down for a name that is no rehearsal's must fail"
    assert "porelo-vm delete" not in calls and "virsh" not in calls, "nothing is asked of libvirt"


def test_the_tunnel_takes_only_the_runs_host_key_and_refuses_once_it_is_gone(tmp_path, monkeypatch):
    """Prevent the tunnel trusting the person's own known hosts for the VM's address."""
    state, call = rehearsal(tmp_path)
    state.mkdir(parents=True)
    (state / "address").write_text("192.0.2.10\n")
    known = state / "known_hosts"
    known.write_text("192.0.2.10 ssh-ed25519 AAAA\n")
    monkeypatch.setenv("ROOM_TUNNEL_ONCE", "1")
    done, calls = call("tunnel", "alice", "8448")
    assert done.returncode == 0, done.stderr
    tunnel = [line for line in calls.splitlines() if line.startswith("ssh ")]
    assert len(tunnel) == 1 and f"UserKnownHostsFile={known}" in tunnel[0], "the run's host key alone is trusted"
    assert "StrictHostKeyChecking=yes" in tunnel[0] and tunnel[0].endswith("alice@192.0.2.10")
    known.unlink()
    done, calls_after = call("tunnel", "alice", "8448")
    assert calls_after == calls, "no ssh runs once the run's host key is gone"
