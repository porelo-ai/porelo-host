"""Prevent a rehearsal testing a stale privileged package or accepting an unclean host."""

import json
import ast
import os
from pathlib import Path
import subprocess
import sys

import jinja2
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def verify_tasks():
    return yaml.safe_load((ROOT / "extensions/molecule/default/verify.yml").read_text())[0]["tasks"]


def test_verify_refuses_the_wrong_host_version_and_every_legacy_program():
    """Refuse a different privileged build or a legacy program surviving an upgrade."""
    tasks = verify_tasks()
    version = next(t for t in tasks if t.get("register") == "verify_host_program_version")
    assert version["ansible.builtin.command"]["argv"][-2:] == ["/usr/sbin/porelo-host", "--version"]
    assert version["ansible.builtin.command"]["argv"][:2] == ["env", "-i"]
    assertion = next(
        t["ansible.builtin.assert"] for t in tasks if t.get("name") == "Assert the pinned host program version"
    )
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    check = env.compile_expression(assertion["that"])
    assert check(verify_host_program_version={"stdout": "porelo-host pinned"}, verify_host_version="pinned")
    assert not check(verify_host_program_version={"stdout": "porelo-host stale"}, verify_host_version="pinned")
    legacy = next(t for t in tasks if t.get("register") == "verify_legacy_programs")
    assert legacy["ansible.builtin.stat"]["follow"] is False
    assert set(legacy["loop"]) == {
        "/usr/local/sbin/porelo-host-person",
        "/usr/local/sbin/porelo-host-project",
        "/usr/local/libexec/porelo-forge-gate",
        "/usr/local/sbin/porelo-host-push",
        "/usr/local/bin/porelo-host-forge-token",
        "/usr/local/share/porelo-host-forge-token.sh",
        "/usr/local/bin/porelo-host-stop",
        "/usr/local/libexec/porelo-host/porelo-pool-revert",
        "/usr/local/libexec/porelo-host/porelo-vm",
        "/usr/local/sbin/porelo-host-forge-password",
    }
    assertion = next(t for t in tasks if t.get("name") == "Assert no legacy host program remains")
    assert assertion["loop"] == "{{ verify_legacy_programs.results }}"
    checks = [env.compile_expression(c) for c in assertion["ansible.builtin.assert"]["that"]]
    for exists, link in [(False, False), (True, False), (False, True)]:
        assert all(c(item={"stat": {"exists": exists, "islnk": link}}) for c in checks) is not (exists or link)


@pytest.fixture
def package_inputs(tmp_path):
    bins = tmp_path / "bin"
    bins.mkdir()
    reader = bins / "dpkg-deb"
    reader.write_text(
        f"#!{sys.executable}\nimport json, pathlib, sys\n"
        "assert sys.argv[1] == '--field'\n"
        "print(json.loads(pathlib.Path(sys.argv[2]).read_text())[sys.argv[3]])\n"
    )
    reader.chmod(0o755)
    packages = tmp_path / "packages"
    packages.mkdir()
    (packages / "porelo.deb").write_text(json.dumps({"Package": "porelo", "Version": "0.5.1~snapshot.1"}))
    host = tmp_path / "host package.deb"
    host.write_text(json.dumps({"Package": "porelo-host", "Version": "0.5.1~snapshot.2"}))
    environment = {
        **os.environ,
        "PATH": f"{bins}:{os.environ['PATH']}",
        "PORELO_HOST_PACKAGES": str(packages),
        "PORELO_HOST_DEB": str(host),
    }
    return host, environment


def stage(tmp_path, environment):
    dest = tmp_path / "staged"
    done = subprocess.run(
        ["sh", str(ROOT / "build/stage-packages.sh"), str(dest)],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    return done, dest


def test_local_host_package_is_required_before_staging(tmp_path, package_inputs):
    """Refuse a run that could silently fall back to a different published host program."""
    unused, environment = package_inputs
    environment.pop("PORELO_HOST_DEB")
    done, dest = stage(tmp_path, environment)
    assert done.returncode != 0 and "PORELO_HOST_DEB" in done.stderr
    assert not dest.exists()


def test_both_local_programs_and_their_exact_versions_are_staged(tmp_path, package_inputs):
    host, environment = package_inputs
    done, dest = stage(tmp_path, environment)
    assert done.returncode == 0, done.stderr
    assert (dest / "porelo-host.deb").read_bytes() == host.read_bytes()
    assert (dest / "porelo.deb").exists()
    assert (dest / "porelo-host.version").read_text().strip() == "0.5.1~snapshot.2"
    assert (dest / "porelo.version").read_text().strip() == "0.5.1~snapshot.1"


def test_a_different_package_cannot_impersonate_the_host_program(tmp_path, package_inputs):
    """Prevent installing the wrong local artifact as the privileged host program."""
    host, environment = package_inputs
    host.write_text(json.dumps({"Package": "unrelated", "Version": "1"}))
    done, dest = stage(tmp_path, environment)
    assert done.returncode != 0 and "PORELO_HOST_DEB" in done.stderr
    assert not dest.exists()


def test_multiline_versions_never_reach_inventory(tmp_path, package_inputs):
    """Prevent package metadata from injecting additional host inventory settings."""
    host, environment = package_inputs
    host.write_text(json.dumps({"Package": "porelo-host", "Version": "1\nextra: setting"}))
    done, dest = stage(tmp_path, environment)
    assert done.returncode != 0 and "Version" in done.stderr
    assert not dest.exists()


def test_conflicting_host_artifacts_are_refused(tmp_path, package_inputs):
    """Prevent a packages directory from silently replacing the explicitly selected host build."""
    unused, environment = package_inputs
    (Path(environment["PORELO_HOST_PACKAGES"]) / "other-host.deb").write_text(
        json.dumps({"Package": "porelo-host", "Version": "0.5.1~snapshot.1"})
    )
    done, dest = stage(tmp_path, environment)
    assert done.returncode != 0 and "conflicting" in done.stderr
    assert not dest.exists()


def test_follow_act_uses_native_follow_and_json_status():
    """Prevent silent acceptance skips or a human status answer being parsed as JSON."""
    source = (ROOT / "extensions/molecule/default/files/follow_act.py").read_text()
    tree = ast.parse(source)
    commands = [
        tuple(arg.value for arg in node.args if isinstance(arg, ast.Constant))
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "helper"
    ]
    assert ("org", "follow") in commands
    assert ("org", "status", "--json") in commands
    assert not any(command[:1] == ("purge",) for command in commands)


def test_follow_act_asks_follow_now_as_a_person_and_as_nobody():
    """Prevent a person's follow-now sudo rule going unexercised, or a refusal of anyone else going unchecked."""
    tree = ast.parse((ROOT / "extensions/molecule/default/files/follow_act.py").read_text())
    commands = [
        tuple(arg.value if isinstance(arg, ast.Constant) else ast.unparse(arg) for arg in node.args)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "run"
    ]
    for login in ("fb", "nobody"):
        assert ("runuser", "-u", login, "--", "sudo", "-n", "HELPER", "org", "follow-now") in commands


def test_the_scenario_holds_no_task_that_never_runs():
    """Prevent a lack of the host program hiding as a task that is skipped in every run."""
    scenario = ROOT / "extensions/molecule/default"
    dead = []
    for path in sorted(scenario.glob("**/*.yml")):
        stack = [yaml.safe_load(path.read_text())]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if node.get("when") is False:
                    dead.append(f"{path.name}: {node.get('name')}")
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    assert not dead


def test_molecule_invokes_no_removed_program():
    """Prevent a scenario from reaching an unversioned privileged entry point."""
    removed = [
        "porelo-host-person",
        "porelo-host-project",
        "porelo-host-push",
        "porelo-host-stop",
        "porelo-host-forge-token",
        "porelo-forge-gate",
        "porelo-pool-revert",
    ]

    def walk(tasks):
        for task in tasks:
            yield task
            for key in ("block", "rescue", "always"):
                yield from walk(task.get(key, []))

    for path in (ROOT / "extensions/molecule/default").rglob("*.yml"):
        data = yaml.safe_load(path.read_text())
        if not isinstance(data, list):
            continue
        for entry in data:
            for task in walk(entry.get("tasks", [entry])):
                for module in ("ansible.builtin.command", "ansible.builtin.shell", "ansible.builtin.script"):
                    command = str(task.get(module, ""))
                    # Unit names in systemctl/journalctl remain collection configuration.
                    for name in removed:
                        assert f"/usr/local/sbin/{name}" not in command, path
                        assert f"/usr/local/libexec/{name}" not in command, path
                        assert f"/usr/local/bin/{name}" not in command, path
                    assert "porelo-host-stop --stdin" not in command, path


def packages_block(tmp_path, package_inputs):
    """The up script's local package part, run against a staged set with root's paths under tmp_path."""
    unused, environment = package_inputs
    text = (ROOT / "build/rehearse-move.sh").read_text()
    begin = text.index('if [ -n "$digest" ]; then\n')
    end = text.index("\nfi\n", begin) + 4
    root = tmp_path / "root"
    root.mkdir()
    block = text[begin:end].replace("/root/", f"{root}/")
    done, staged = stage(tmp_path, environment)
    assert done.returncode == 0, done.stderr
    staging = tmp_path / "remote-staging"
    staging.mkdir()
    subprocess.run(["tar", "-C", str(staged), "-cf", str(staging / "porelo-packages.tar"), "."], check=True)
    digest = subprocess.run(
        ["sha256sum", str(staged / "SHA256SUMS")], capture_output=True, text=True, check=True
    ).stdout.split()[0]
    script = "set -euo pipefail\nstaging=$1 digest=$2\n" + block

    def run(given_digest=digest):
        return subprocess.run(
            ["bash", "-c", script, "up", str(staging), given_digest], capture_output=True, text=True, check=False
        )

    return run, root, staging, digest


def test_rehearse_move_takes_its_vm_tool_from_build():
    """Prevent the rehearsal calling the VM tool from the role directory the collection no longer holds."""
    text = (ROOT / "build/rehearse-move.sh").read_text()
    assert "vm=$root/build/porelo-vm" in text and "roles/vm_pool/files/porelo-vm" not in text
    assert (ROOT / "build/porelo-vm").is_file()


def test_staged_packages_reach_up_as_its_local_packages_and_pins(tmp_path, package_inputs):
    """Prevent a rehearsal installing a published host program in place of the staged one."""
    run, root, staging, digest = packages_block(tmp_path, package_inputs)
    done = run()
    assert done.returncode == 0, done.stderr
    inventory = (root / "porelo-host-inventory.yml.tmp").read_text()
    assert f"    porelo_local_packages: {root}/porelo-packages-{digest}\n" in inventory
    assert '    porelo_host_version: "0.5.1~snapshot.2"\n' in inventory
    assert '    porelo_version: "0.5.1~snapshot.1"\n' in inventory
    assert not (staging / "porelo-packages.tar").exists()


def test_remote_package_sets_use_separate_directories(tmp_path, package_inputs):
    """Prevent a package removed from a later handover from being installed out of an old cache."""
    run, root, unused_staging, digest = packages_block(tmp_path, package_inputs)
    (root / f"porelo-packages-{digest}").mkdir()
    (root / f"porelo-packages-{digest}/stale.deb").write_text("left from an older set")
    assert run().returncode == 0
    assert not (root / f"porelo-packages-{digest}/stale.deb").exists()
    converge = yaml.safe_load((ROOT / "extensions/molecule/default/converge.yml").read_text())[0]
    assert "hash('sha256')" in converge["vars"]["converge_remote_packages"]


def test_a_package_set_other_than_the_staged_one_is_refused(tmp_path, package_inputs):
    """Prevent up running on packages that changed on their way to the host."""
    run, root, unused_staging, digest = packages_block(tmp_path, package_inputs)
    other = ("0" if digest[0] != "0" else "1") + digest[1:]
    assert run(other).returncode != 0
    assert not (root / "porelo-host-inventory.yml.tmp").exists()


def test_local_installation_refreshes_its_new_repository_before_dependencies():
    """Prevent fresh hosts from failing to resolve dependencies of the supplied local packages."""
    tasks = yaml.safe_load((ROOT / "roles/porelo/tasks/install.yml").read_text())
    refresh = next(
        i
        for i, t in enumerate(tasks)
        if t.get("ansible.builtin.apt", {}).get("update_cache")
        and t.get("when") == "porelo_local_packages | length > 0"
    )
    install = next(i for i, t in enumerate(tasks) if t.get("register") == "__porelo_local_installed")
    assert refresh < install


def _workflow_molecule_run(text):
    steps = yaml.safe_load(text)["jobs"]["molecule"]["steps"]
    return next(s for s in steps if s.get("name") == "The Molecule scenario on its VM")["run"]


def test_the_runner_stages_the_pinned_published_packages_before_molecule():
    """GitHub's runner has no local hand-over: Molecule refuses without PORELO_HOST_DEB, so CI fetches the pin."""
    run = _workflow_molecule_run((ROOT / ".github/workflows/build.yml").read_text())
    lines = [line.strip() for line in run.splitlines() if line.strip()]
    fetch = next(i for i, line in enumerate(lines) if "build/fetch-host-deb.sh" in line)
    assert lines[fetch].startswith("PORELO_HOST_DEB=$(build/fetch-host-deb.sh ")
    assert "export PORELO_HOST_DEB PORELO_HOST_PACKAGES" in lines
    assert lines.index("build/molecule.sh") > fetch
    assert lines[0] == "set -eu"


def test_fetch_host_deb_reads_every_pin_it_needs_from_the_role():
    """The fetch takes version, repository, key and fingerprint from the role's defaults, never its own copy."""
    defaults = yaml.safe_load((ROOT / "roles/porelo/defaults/main.yml").read_text())
    script = (ROOT / "build/fetch-host-deb.sh").read_text()
    for pin in ("porelo_host_version", "porelo_repository_url", "porelo_key_url", "porelo_key_fingerprint"):
        assert f"pinned {pin}" in script and pin in defaults
    assert defaults["porelo_key_fingerprint"] not in script and "jfrog" not in script
    assert "--with-colons --show-keys" in script and "signed-by=" in script
