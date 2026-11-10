"""Guard what up installs for the people's Porelo, as porelo-setup.sh would."""

from pathlib import Path
import subprocess
import sys

import jinja2
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_up_installs_what_porelo_setup_always_installs():
    """Prevent a host whose apt skips recommended packages from giving people a Porelo without filter or networking.

    porelo-host-person makes the account itself, with each person's own subordinate ID range; porelo-setup.sh
    --user would give every person the same one. The packages the script always installs come from up instead.
    """
    tasks = yaml.safe_load((ROOT / "roles/porelo/tasks/install.yml").read_text())
    names = set()
    for task in tasks:
        name = task.get("ansible.builtin.apt", {}).get("name")
        names.update([name] if isinstance(name, str) else name or [])
    assert {"porelo={{ porelo_version }}", "porelo-message-sluice-filter", "uidmap", "slirp4netns", "passt"} <= names


def test_up_installs_catatonit_for_the_tasks_init():
    """Prevent a task container started with --init from failing on a host without podman's recommends.

    porelo starts every task container with --init, which needs catatonit; podman only recommends it, and porelo's
    package does not depend on it yet. Both install paths carry it until porelo's Depends does.
    """
    tasks = yaml.safe_load((ROOT / "roles/porelo/tasks/install.yml").read_text())
    apt = [
        task["ansible.builtin.apt"]["name"]
        for task in tasks
        if "ansible.builtin.apt" in task
        and isinstance(task["ansible.builtin.apt"].get("name"), list)
        and "passt" in task["ansible.builtin.apt"]["name"]
    ]
    local = [
        task
        for task in tasks
        if task.get("name") == "install | Install local Porelo packages together with their dependencies"
    ]
    assert apt and all("catatonit" in names for names in apt)
    assert local and "'catatonit'" in local[0]["ansible.builtin.command"]["argv"]


def test_up_installs_every_published_agent_as_the_repository_lists_them():
    """Prevent a list kept by hand from missing a new agent, or the acceptance suite's stub from being installed.

    The operator's decision: up installs every published agent package. Each declares Provides: porelo-agent, the
    stub deliberately not, which is how Porelo's setup script and daemon read the repository as the catalogue.
    """
    tasks = yaml.safe_load((ROOT / "roles/porelo/tasks/install.yml").read_text())
    reads = [task for task in tasks if "apt-cache showpkg porelo-agent" in str(task.get("ansible.builtin.command"))]
    assert len(reads) == 1 and reads[0].get("changed_when") is False
    names = [task for task in tasks if reads[0]["register"] in str(task.get("ansible.builtin.set_fact", {}))]
    assert len(names) == 1
    (fact,) = names[0]["ansible.builtin.set_fact"]
    installs = [task for task in tasks if task.get("ansible.builtin.apt", {}).get("name") == "{{ " + fact + " }}"]
    assert len(installs) == 1
    assert tasks.index(reads[0]) < tasks.index(names[0]) < tasks.index(installs[0])


@pytest.mark.parametrize("relation,accepted", [("older", False), ("equal", True), ("newer", True)])
def test_up_refuses_an_older_host_program_with_both_versions(tmp_path, monkeypatch, relation, accepted):
    """Prevent incompatible privileged commands being started after an incomplete package upgrade."""
    tasks = yaml.safe_load((ROOT / "roles/porelo/tasks/install.yml").read_text())
    monkeypatch.setenv("PATH", str(tmp_path))
    defaults = yaml.safe_load((ROOT / "roles/porelo/defaults/main.yml").read_text())
    required = defaults["porelo_host_version"]
    installed = {"older": "0~older", "equal": required, "newer": "9999"}[relation]
    calls = tmp_path / "dpkg-arguments"
    dpkg = tmp_path / "dpkg"
    dpkg.write_text(
        f"#!{sys.executable}\n"
        "import pathlib, sys\n"
        f"expected = {['--compare-versions', installed, 'ge', required]!r}\n"
        "if sys.argv[1:] != expected: sys.exit(2)\n"
        f"pathlib.Path({str(calls)!r}).write_text('called')\n"
        f"sys.exit({0 if accepted else 1})\n"
    )
    dpkg.chmod(0o755)
    compare = next(t for t in tasks if t.get("register") == "__porelo_host_version_comparison")
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    values = {"porelo_host_version": required, "__porelo_host_package": {"stdout": installed}}
    argv = [env.from_string(arg).render(**values) for arg in compare["ansible.builtin.command"]["argv"]]
    done = subprocess.run(argv, capture_output=True, text=True, check=False)
    assert calls.read_text() == "called", "the comparison must use the isolated stand-in, never a host dpkg"
    assert (done.returncode == 0) is accepted, (argv, done.stderr)
    refusal = next(
        t["ansible.builtin.assert"]
        for t in tasks
        if "version" in t.get("name", "").lower() and "ansible.builtin.assert" in t
    )
    values["__porelo_host_version_comparison"] = {"rc": done.returncode}
    assert env.compile_expression(refusal["that"])(**values) is accepted
    message = env.from_string(refusal["fail_msg"]).render(**values)
    assert installed in message and required in message
    names = [t.get("ansible.builtin.apt", {}).get("name", []) for t in tasks]
    assert any("porelo-host={{ porelo_host_version }}" in name for name in names)
