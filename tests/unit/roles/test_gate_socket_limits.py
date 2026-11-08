"""Keep every connection-per-process gate socket listening under a burst, as move 3's forge page did not."""

import configparser
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]

GATE_SOCKETS = sorted(
    path for path in (ROOT / "roles").glob("*/templates/*.socket.j2") if "Accept=yes" in path.read_text()
)


def socket_section(path):
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.optionxform = str
    parser.read_string("\n".join(line for line in path.read_text().splitlines() if not line.startswith("{{")))
    return parser["Socket"]


def test_every_gate_socket_is_found():
    names = {path.name for path in GATE_SOCKETS}
    assert names == {
        "porelo-forge-web.socket.j2",
        "porelo-forge-git.socket.j2",
        "porelo-forge-runner.socket.j2",
        "porelo-host-verify.socket.j2",
        "porelo-matrix-gate.socket.j2",
    }


@pytest.mark.parametrize("path", GATE_SOCKETS, ids=lambda path: path.name)
def test_a_burst_of_connections_never_fails_the_socket_for_good(path):
    """systemd's trigger limit fails the socket and RemoveOnStop deletes it: every later request is empty."""
    assert socket_section(path).get("TriggerLimitIntervalSec") == "0"


@pytest.mark.parametrize("path", GATE_SOCKETS, ids=lambda path: path.name)
def test_the_connections_at_once_are_bounded_explicitly(path):
    """Not systemd's default 64: the people's and the runner's gates fit a browser's pages and polls, the judge 16."""
    value = socket_section(path).get("MaxConnections")
    assert value == ("16" if "verify" in path.name else "256")


def listening_check(tasks_file, name, after):
    """The check, with every unit and path, after the units start and their handlers ran, and never skipped."""
    tasks = yaml.safe_load((ROOT / tasks_file).read_text())
    names = [task.get("name", "") for task in tasks]
    checks = [index for index, task in enumerate(names) if task == name]
    assert len(checks) == 1
    check = tasks[checks[0]]
    assert "when" not in check
    flushes = [index for index, task in enumerate(tasks) if task.get("ansible.builtin.meta") == "flush_handlers"]
    assert names.index(after) < checks[0]
    assert any(names.index(after) < index < checks[0] for index in flushes)
    return " ".join(check["ansible.builtin.command"]["argv"])


def assert_checks(script, units, paths):
    for unit in units:
        assert unit in script
    for path in paths:
        assert path in script
    assert "systemctl is-active --quiet" in script
    assert "test -S" in script
    assert script.count("exit 1") >= 2


def test_up_checks_that_every_forge_gate_socket_listens():
    script = listening_check(
        "roles/forge/tasks/service.yml",
        "service | Check that the gate sockets listen",
        "service | Enable and start the gate sockets after Forgejo answers",
    )
    assert_checks(
        script,
        [
            "porelo-forge-web.socket",
            "porelo-forge-git.socket",
            "porelo-forge-runner.socket",
            "porelo-host-verify.socket",
        ],
        [
            "/run/porelo-forge/web.sock",
            "/run/porelo-forge/git.sock",
            "/run/porelo-forge/runner.sock",
            "/run/porelo-host/verify/verify.sock",
        ],
    )


def test_up_checks_that_the_matrix_gate_socket_listens():
    script = listening_check(
        "roles/matrix/tasks/main.yml",
        "Check that the Matrix gate socket listens",
        "Enable and start the Matrix gate socket",
    )
    assert_checks(script, ["porelo-matrix-gate.socket"], ["/run/porelo-matrix/client.sock"])
