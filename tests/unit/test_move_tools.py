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
