"""Every podman call as a service account reaches that account's user manager by its session bus."""

import os
import re
import runpy
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
ROLES = ROOT / "roles"


def test_every_runtime_the_roles_set_names_its_session_bus_beside_it():
    """Prevent a role from leaving podman to fall back to the cgroupfs manager, which crun refuses."""
    found = 0
    for path in sorted([*ROLES.rglob("*.yml"), *ROLES.glob("*/files/*")]):
        text = path.read_text()
        for runtime in re.findall(
            r"XDG_RUNTIME_DIR[=:] ?\"?(/run/user/(?:\{\{ [^}]+ \}\}|\$\(id -u\)|[^\s\"\\]+))", text
        ):
            assert f"DBUS_SESSION_BUS_ADDRESS=unix:path={runtime}/bus" in text or (
                f'DBUS_SESSION_BUS_ADDRESS: "unix:path={runtime}/bus"' in text
            ), f"{path.relative_to(ROOT)} sets XDG_RUNTIME_DIR={runtime} without its session bus"
            found += 1
    assert found >= 10


def test_the_roles_wait_for_each_service_accounts_bus_before_its_containers():
    """Prevent a missing user manager from surfacing as crun's cgroup error instead of the account's name."""
    for path, task in (
        ("roles/forge/tasks/accounts.yml", "accounts | Wait for each account's user manager and its session bus"),
        ("roles/matrix/tasks/main.yml", "Wait for the homeserver account's user manager and its session bus"),
    ):
        tasks = yaml.safe_load((ROOT / path).read_text())
        names = [item["name"] for item in tasks]
        waiting = tasks[names.index(task)]["ansible.builtin.wait_for"]
        assert waiting["path"].startswith("/run/user/") and waiting["path"].endswith("/bus")
        assert "has no session bus" in waiting["msg"]
        started = tasks[names.index(task) - 1]["ansible.builtin.systemd_service"]
        assert started["name"].startswith("user@") and started["state"] == "started"
        linger = next(i for i, name in enumerate(names) if "linger" in name)
        first_account_task = min((i for i, item in enumerate(tasks) if "environment" in item), default=len(tasks))
        assert linger < names.index(task) - 1 and names.index(task) < first_account_task


@pytest.mark.parametrize("bus", ["socket", "missing", "file"])
def test_the_project_helper_refuses_a_forge_account_without_its_bus(tmp_path, monkeypatch, bus):
    """Prevent porelo-host-project from running podman as the forge account with no user manager bus."""
    namespace = runpy.run_path(str(ROLES / "forge/files/porelo-host-project"), run_name="session_bus_tests")
    values = namespace["forge_command"].__globals__
    path = tmp_path / "1234/bus"
    path.parent.mkdir()
    if bus == "socket":
        os.mknod(path, stat.S_IFSOCK | 0o600)
    elif bus == "file":
        path.write_text("")
    calls = []

    def run(arguments, **_kwargs):
        calls.append(arguments)
        if arguments[:2] == ["/usr/bin/id", "-u"]:
            return SimpleNamespace(returncode=0, stdout="1234\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    values["RUN_USER"] = str(tmp_path)
    monkeypatch.setattr(values["subprocess"], "run", run)
    if bus == "socket":
        namespace["forge_command"]("porelo-forge", "list")
        assert "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1234/bus" in calls[-1]
        assert "XDG_RUNTIME_DIR=/run/user/1234" in calls[-1]
    else:
        with pytest.raises(values["Refusal"]) as refused:
            namespace["forge_command"]("porelo-forge", "list")
        assert refused.value.code == 69 and "porelo-forge has no session bus" in str(refused.value)
        assert all("/usr/bin/podman" not in call for call in calls)


def test_matrix_down_stops_the_homeserver_unit_only_through_a_running_manager():
    """Prevent down from failing at systemctl --user where a runtime directory has no user manager behind it."""
    tasks = yaml.safe_load((ROLES / "matrix/tasks/down.yml").read_text())
    probe = next(item for item in tasks if item.get("register") == "__matrix_down_runtime")
    assert probe["ansible.builtin.stat"]["path"].endswith("/bus")
    stop = next(item for item in tasks if "__matrix_down_runtime.stat.issock | default(false)" in item.get("when", []))
    assert stop["ansible.builtin.systemd_service"]["scope"] == "user"
