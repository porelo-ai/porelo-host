"""Prevent service execution of removed programs and disabled native acceptance."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "path,command",
    [
        ("porelo/templates/porelo-host-follow.service.j2", "/usr/sbin/porelo-host org follow"),
        (
            "forge/templates/porelo-forge-web@.service.j2",
            "/usr/sbin/porelo-host forge gate --web --upstream {{ __forge_socket }}",
        ),
        (
            "forge/templates/porelo-forge-git@.service.j2",
            "/usr/sbin/porelo-host forge gate --git --upstream {{ __forge_socket }}",
        ),
        (
            "forge/templates/porelo-forge-runner@.service.j2",
            "/usr/sbin/porelo-host forge gate --runner --upstream {{ __forge_socket }}",
        ),
        (
            "vm_pool/templates/porelo-pool-revert.service.j2",
            "/usr/sbin/porelo-host pool revert {{ __vm_pool_etc }}/vms",
        ),
    ],
)
def test_units_execute_the_pinned_native_program(path, command):
    """Prevent cleanup leaving enabled units pointing to missing executables."""
    assert f"ExecStart={command}\n" in (ROOT / "roles" / path).read_text()


def test_hook_is_installed_at_the_follow_link_target():
    """Prevent every repository push failing because the native follow links a missing hook."""
    tasks = yaml.safe_load((ROOT / "roles/forge/tasks/service.yml").read_text())
    hook = next(t["ansible.builtin.copy"] for t in tasks if "ansible.builtin.copy" in t)
    assert hook["dest"] == "/usr/local/libexec/porelo/pre-receive"
    assert (
        "Volume=/usr/local/libexec/porelo/pre-receive:{{ __forge_push_hook }}:ro"
        in (ROOT / "roles/forge/templates/forgejo.container.j2").read_text()
    )


def test_pool_acceptance_and_follow_are_enabled():
    """Prevent a green scenario that omits the package's lifecycle acceptance."""
    tasks = yaml.safe_load((ROOT / "extensions/molecule/default/verify.yml").read_text())[0]["tasks"]
    pool = [t for t in tasks if "pool commands unavailable" in t.get("name", "")]
    assert not pool
    registers = {t["register"]: t for t in tasks if "register" in t}
    expected = {
        "verify_pool_file",
        "verify_pool_file_stat",
        "verify_pool_key",
        "verify_pool_seed",
        "verify_pool_restarts",
        "verify_pool_old",
        "verify_pool_revert_log",
    }
    assert expected <= registers.keys()
    assert all(registers[name].get("when") == "verify_vm_pool == 'on'" for name in expected)
    nested = tasks + [child for t in tasks for child in t.get("block", [])]
    follow = next(t for t in nested if t.get("ansible.builtin.include_tasks", "").endswith("/tasks/follow.yml"))
    assert follow.get("when") is not False


def test_a_host_package_without_the_push_judge_is_refused_before_upgrade_cleanup():
    """Prevent an upgrade deleting executable targets of still-active legacy units."""
    tasks = yaml.safe_load((ROOT / "roles/porelo/tasks/install.yml").read_text())
    cleanup = next(i for i, t in enumerate(tasks) if "legacy_programs.yml" in str(t))
    refusal = next(i for i, t in enumerate(tasks) if "__porelo_host_version_comparison.rc == 0" in str(t))
    assert refusal < cleanup
    defaults = yaml.safe_load((ROOT / "roles/porelo/defaults/main.yml").read_text())
    # A host installs from Porelo's repository, which publishes snapshots by run number and never a local build's
    # +local version. 462 (porelo 7b1517f20) is the first published with the judge-push verb, socket-started units
    # under systemd 258+ and a task's push of its own branch.
    release, snapshot = re.fullmatch(r"([0-9.]+)~snapshot\.([0-9]+)", defaults["porelo_host_version"]).groups()
    assert (release, int(snapshot) >= 462) == ("0.5.1", True)


def test_expected_follow_refusals_are_not_counted_as_failures():
    """Prevent correct refusal paths from making native acceptance fail."""
    import ast

    source = (ROOT / "extensions/molecule/default/files/follow_act.py").read_text()
    tree = ast.parse(source)
    functions = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    namespace = {"WRONG": [], "HELPER": "/usr/sbin/porelo-host"}
    from types import SimpleNamespace

    namespace["run"] = lambda *a, **kw: SimpleNamespace(returncode=65, stdout="", stderr="refused-state")
    exec(compile(ast.Module(body=[functions["check"], functions["helper"]], type_ignores=[]), "act", "exec"), namespace)
    namespace["helper"]("org", "follow", expected=65)
    assert not namespace["WRONG"]


def test_fixture_installation_and_execution_share_restoration():
    """Prevent a failed fixture installation leaving the installed CLI diverted."""
    tasks = yaml.safe_load((ROOT / "extensions/molecule/default/verify.yml").read_text())[0]["tasks"]
    block = next((t for t in tasks if any("org_standin.yml" in str(child) for child in t.get("block", []))), None)
    assert block is not None
    assert any("follow.yml" in str(t) for t in block["block"])
    assert any("dpkg-divert" in str(t) for t in block.get("always", []))


def _argvs(node):
    """Every command argv in a task file, those in blocks among them."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "argv" and isinstance(value, list):
                yield value
            else:
                yield from _argvs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _argvs(item)


def test_every_task_calls_the_host_program_with_an_empty_environment():
    """Prevent an Ansible run's own variables, ANSIBLE_STDOUT_CALLBACK among them, reaching porelo-host.

    porelo-host refuses any variable outside its list (exit 78), and `up` and `down` run with the lines callback set.
    """
    helpers = {"/usr/sbin/porelo-host", "{{ __vm_pool_project_helper }}"}
    calls = []
    for path in [
        *ROOT.glob("playbooks/*.yml"),
        *ROOT.glob("roles/*/tasks/*.yml"),
        *ROOT.glob("roles/*/handlers/*.yml"),
    ]:
        for argv in _argvs(yaml.safe_load(path.read_text())):
            words = [str(word) for word in argv]
            if helpers & set(words):
                calls.append((path.relative_to(ROOT), words))
    assert len(calls) >= 8, calls
    for path, words in calls:
        assert words[:3] == ["env", "-i", "PATH=/usr/sbin:/usr/bin:/sbin:/bin"], f"{path}: {words}"
