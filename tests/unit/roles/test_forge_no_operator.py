"""Guard the forge role against pre-creating a forge login for a person."""

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
