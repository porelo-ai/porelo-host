"""Guard the forge role against pre-creating or keeping an unrecorded operator login."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def collection_yaml_files():
    paths = sorted((ROOT / "playbooks").glob("*.yml"))
    for subdir in ("tasks", "defaults", "vars", "handlers", "meta"):
        paths.extend(sorted((ROOT / "roles").glob(f"*/{subdir}/*.yml")))
    return paths


def test_no_task_or_role_setting_names_forge_person():
    """Prevent any role or playbook from reserving forge_person or writing person= into forge.conf."""
    paths = collection_yaml_files()
    relative = {path.relative_to(ROOT).as_posix() for path in paths}
    expected = {
        "playbooks/up.yml",
        "roles/forge/defaults/main.yml",
        "roles/forge/meta/argument_specs.yml",
        "roles/forge/tasks/main.yml",
        "roles/forge/tasks/settings.yml",
    }
    assert expected <= relative
    offenders = [path.relative_to(ROOT).as_posix() for path in paths if "forge_person" in path.read_text()]
    assert offenders == []

    request_tasks = yaml.safe_load((ROOT / "roles/forge/tasks/settings.yml").read_text())
    forge_conf = next(
        task["ansible.builtin.copy"]["content"]
        for task in request_tasks
        if task.get("ansible.builtin.copy", {}).get("dest") == "/etc/porelo-host/forge.conf"
    )
    keys = [
        line.strip().split("=", 1)[0]
        for line in forge_conf.splitlines()
        if "=" in line and not line.strip().startswith("{%")
    ]
    assert keys == ["host", "name", "port", "git_port", "account"]


def test_up_deletes_only_an_unrecorded_operator_forge_user_and_installs_helpers():
    """Prevent an upgraded host from keeping an unrecorded operator account or deleting an admitted operator."""
    main_tasks = yaml.safe_load((ROOT / "roles/forge/tasks/main.yml").read_text())
    included_files = []
    tasks = []
    for entry in main_tasks:
        target = entry.get("ansible.builtin.include_tasks")
        if isinstance(target, str) and target.startswith("{{ role_path }}/"):
            rel = target.removeprefix("{{ role_path }}/")
            included_files.append(rel)
            tasks.extend(yaml.safe_load((ROOT / "roles/forge" / rel).read_text()))

    assert "tasks/admin.yml" in included_files

    installed = {
        task["ansible.builtin.copy"]["dest"]: task["ansible.builtin.copy"]
        for task in tasks
        if "ansible.builtin.copy" in task and "dest" in task["ansible.builtin.copy"]
    }
    for helper in ("/usr/local/sbin/porelo-host-project",):
        assert helper in installed
        assert installed[helper]["owner"] == "root"
        assert installed[helper]["group"] == "root"
        assert installed[helper]["mode"] == "0700"

    stat_index, stat_task = next(
        (
            (index, task)
            for index, task in enumerate(tasks)
            if task.get("ansible.builtin.stat", {}).get("path") == "/etc/porelo-host/people/operator.conf"
        ),
        (None, None),
    )
    assert stat_task is not None, "missing stat guard on /etc/porelo-host/people/operator.conf"
    assert stat_task["ansible.builtin.stat"].get("follow") is False
    record_var = stat_task["register"]

    delete_index, delete_task = next(
        (
            (index, task)
            for index, task in enumerate(tasks)
            if task.get("ansible.builtin.command", {}).get("argv")
            == ["podman", "exec", "forgejo", "forgejo", "admin", "user", "delete", "--username", "operator", "--purge"]
        ),
        (None, None),
    )
    assert delete_task is not None, "missing Forgejo delete task for unrecorded operator user"
    assert delete_index > stat_index
    conditions = delete_task.get("when", [])
    if isinstance(conditions, str):
        conditions = [conditions]
    joined = " && ".join(conditions)
    assert f"not {record_var}.stat.exists" in joined
    assert f"{record_var}.stat.islnk" in joined
    assert "'operator' in" in joined
    assert delete_task.get("no_log") is True


def test_password_helper_is_removed_instead_of_installed():
    """Prevent an upgrade from keeping a privileged route to set forge passwords."""
    tasks = yaml.safe_load((ROOT / "roles/forge/tasks/helpers.yml").read_text())
    assert any(
        task.get("ansible.builtin.file") == {"path": "/usr/local/sbin/porelo-host-forge-password", "state": "absent"}
        for task in tasks
    )


def test_teardown_stops_the_previous_https_listener_without_an_upgrade():
    """Prevent an old public listener from surviving a direct teardown."""
    tasks = yaml.safe_load((ROOT / "roles/forge/tasks/down.yml").read_text())
    units = next(task["loop"] for task in tasks if "__forge_down_gate_units" == task.get("register"))
    assert set(units) == {
        "porelo-forge-web.socket",
        "porelo-forge-git.socket",
        "porelo-forge-runner.socket",
        "porelo-forge-https.socket",
        "porelo-forge-https.service",
    }
    stop = next(task for task in tasks if task.get("ansible.builtin.systemd_service", {}).get("state") == "stopped")
    assert stop["ansible.builtin.systemd_service"]["enabled"] is False
    assert "__forge_down_gate_units" in stop["loop"]
    removed = set().union(
        *(
            set(task.get("loop", []))
            for task in tasks
            if task.get("ansible.builtin.file", {}).get("path") == "/etc/systemd/system/{{ item }}"
            and task["ansible.builtin.file"].get("state") == "absent"
        )
    )
    assert set(units) <= removed
