"""Prevent unversioned host programs and extra privileged person commands."""

from pathlib import Path
import re
import shlex
import shutil

import jinja2
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
EXCEPTIONS = {
    "porelo-forge-pre-receive",
    "porelo-host-check",
    "porelo-host-measure",
    "porelo-pool-give-back",
}


def walk_tasks(tasks):
    for task in tasks:
        yield task
        for section in ("block", "rescue", "always"):
            yield from walk_tasks(task.get(section, []))


def test_roles_ship_only_the_stated_program_exceptions():
    """Prevent privileged host code bypassing the reviewed package and its version pin."""
    roles = ROOT / "roles"
    paths = sorted(roles.glob("*/tasks/**/*.yml"))
    assert {path.parents[1].name for path in roles.glob("*/tasks/main.yml")} == {
        "base",
        "check",
        "forge",
        "matrix",
        "measure",
        "porelo",
        "vm_pool",
    }
    assert {path.parent.parent.name for path in paths} >= {"porelo", "forge", "vm_pool"}
    assert {path.name for path in roles.glob("*/files/*") if path.name in EXCEPTIONS} == EXCEPTIONS
    offenders = []
    for path in paths:
        for task in walk_tasks(yaml.safe_load(path.read_text()) or []):
            copy = task.get("ansible.builtin.copy", task.get("copy", {}))
            source = copy.get("src")
            if source:
                items = task.get("loop", [""])
                if not isinstance(items, list):
                    offenders.append(f"{path.relative_to(ROOT)}: unresolved copy loop {items}")
                    continue
                for item in items:
                    name = Path(source.replace("{{ item }}", str(item))).name
                    if name not in EXCEPTIONS:
                        offenders.append(f"{path.relative_to(ROOT)}: copies {source} ({item})")
            script = task.get("ansible.builtin.script", task.get("script"))
            if script:
                command = script.get("cmd", "") if isinstance(script, dict) else script
                prefix = re.match(r"\s*{{.*?}}", command, re.S)
                env = jinja2.Environment(undefined=jinja2.StrictUndefined)
                env.filters["quote"] = shlex.quote
                try:
                    if prefix:
                        command = (
                            env.from_string(prefix[0]).render(role_path=str(path.parent.parent))
                            + command[prefix.end() :]
                        )
                    lexer = shlex.shlex(command, posix=True)
                    lexer.whitespace_split = True
                    source = Path(next(lexer)).resolve()
                except (jinja2.TemplateError, ValueError, StopIteration):
                    source = None
                if source != roles / "check/files/porelo-host-check":
                    offenders.append(f"{path.relative_to(ROOT)}: runs copied script {script}")
    assert offenders == [], "Unpackaged host files:\n" + "\n".join(offenders)


def sudoers_lines():
    path = ROOT / "roles/porelo/templates/porelo-host-person.sudoers.j2"
    return [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.startswith(("#", "{{"))]


def test_people_have_exactly_the_five_packaged_sudo_rules():
    """Prevent a person retaining a privileged legacy entry point or broader sudo access."""
    rules = [line for line in sudoers_lines() if not line.startswith("Defaults")]
    assert sorted(rules) == sorted(
        f"%porelo-people ALL=(root) NOPASSWD: /usr/sbin/porelo-host {verb}"
        for verb in ("forge issue-token", "forge lend-token", "task start *", "task end *", "task show *")
    )


def test_host_sudo_commands_reset_the_environment_without_kept_variables():
    """Prevent preserved variables from changing privileged execution or causing the package to refuse every call."""
    defaults = [line for line in sudoers_lines() if line.startswith("Defaults")]
    assert defaults == ["Defaults!/usr/sbin/porelo-host env_reset, !setenv, !env_keep"]


def test_host_program_units_set_no_extra_environment():
    """Prevent systemd unit settings from defeating the program's strict environment boundary."""
    paths = sorted((ROOT / "roles").glob("*/templates/*.service.j2"))
    expected = {
        "porelo-host-task-sweep.service.j2",
        "porelo-host-follow.service.j2",
        "porelo-host-verify@.service.j2",
        "porelo-forge-web@.service.j2",
        "porelo-forge-git@.service.j2",
        "porelo-forge-runner@.service.j2",
        "porelo-pool-revert.service.j2",
    }
    checked = set()
    for path in paths:
        text = path.read_text()
        if path.name in expected or re.search(r"^Exec\w+=.*?/usr/sbin/porelo-host(?:\s|$)", text, re.M):
            checked.add(path.name)
            assert not re.search(r"^\s*(Environment|EnvironmentFile|PassEnvironment)\s*=", text, re.M), path
    assert expected <= checked


def test_a_script_argument_cannot_bypass_the_exception_list(tmp_path, monkeypatch):
    """Prevent an unreviewed privileged script being passed off as the pre-installation check."""
    shutil.copytree(ROOT / "roles", tmp_path / "roles")
    path = tmp_path / "roles/porelo/tasks/unreviewed.yml"
    path.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Unreviewed script",
                    "ansible.builtin.script": "{{ role_path }}/files/unreviewed --label porelo-host-check",
                }
            ]
        )
    )
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    with pytest.raises(AssertionError, match="unreviewed"):
        test_roles_ship_only_the_stated_program_exceptions()
