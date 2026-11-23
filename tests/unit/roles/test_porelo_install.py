"""Guard what up installs for the people's Porelo, as porelo-setup.sh would."""

from ast import literal_eval
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
    names = {name for names, state in program_installs(role_values("releases")) for name in names}
    assert {"porelo=0.5.0", "porelo-message-sluice-filter", "uidmap", "slirp4netns", "passt"} <= names


def test_up_installs_catatonit_for_the_tasks_init():
    """Prevent a task container started with --init from failing on a host without podman's recommends.

    porelo starts every task container with --init, which needs catatonit; podman only recommends it, and porelo's
    package does not depend on it yet. Both install paths carry it until porelo's Depends does.
    """
    tasks = yaml.safe_load((ROOT / "roles/porelo/tasks/install.yml").read_text())
    apt = [
        names
        for channel in ("releases", "snapshots")
        for names, state in program_installs(role_values(channel))
        if "passt" in names
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
    required = role_values("releases")["porelo_host_version"]
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
    names = {name for names, state in program_installs(role_values("releases")) for name in names}
    assert "porelo-host=" + required in names


ENV = jinja2.Environment(undefined=jinja2.StrictUndefined)


def rendered(text, values):
    """A template as Ansible renders it, a list-like result read back as the list it names."""
    value = ENV.from_string(text).render(**values)
    return literal_eval(value) if value.startswith("[") else value


def role_values(channel, **given):
    """The porelo role's install values for an inventory naming a channel and, maybe, versions."""
    defaults = yaml.safe_load((ROOT / "roles/porelo/defaults/main.yml").read_text())
    names = yaml.safe_load((ROOT / "roles/porelo/vars/main.yml").read_text())
    values = {"porelo_host_distribution": channel, "porelo_local_packages": ""}
    values["porelo_distribution"] = rendered(defaults["porelo_distribution"], values)
    for key in ("porelo_version", "porelo_host_version"):
        values[key] = given.get(key, rendered(defaults[key], values))
    for key in ("__porelo_pinned_programs", "__porelo_newest_programs", "__porelo_host_floor"):
        if key in names:
            values[key] = rendered(names[key], values)
    return values


def runs(task, values):
    """Whether a task's when holds for these values."""
    conditions = task.get("when", [])
    conditions = [conditions] if isinstance(conditions, str) else conditions
    return all(ENV.compile_expression(condition)(**values) for condition in conditions)


def program_installs(values):
    """Each apt install of Porelo's own programs that runs: the names it gives apt and the state it asks."""
    tasks = yaml.safe_load((ROOT / "roles/porelo/tasks/install.yml").read_text())
    installs = []
    for task in tasks:
        apt = task.get("ansible.builtin.apt", {})
        programs = ("porelo_version", "__porelo_pinned_programs", "__porelo_newest_programs")
        if "name" not in apt or not any(word in str(apt["name"]) for word in programs) or not runs(task, values):
            continue
        name = apt["name"]
        names = rendered(name, values) if isinstance(name, str) else [rendered(item, values) for item in name]
        installs.append((names, apt.get("state", "present")))
    return installs


def test_the_snapshots_channel_without_versions_installs_its_newest():
    """Prevent up failing on the release pin porelo=0.5.0, which the snapshots channel does not hold."""
    values = role_values("snapshots")
    installs = program_installs(values)
    newest = {name for names, state in installs if state == "latest" for name in names}
    assert {"porelo", "porelo-host"} <= newest, installs
    named = [name for names, state in installs for name in names if name.startswith(("porelo=", "porelo-host="))]
    assert not named, "no version may be pinned the inventory did not name"


@pytest.mark.parametrize(
    "channel,given",
    [
        ("releases", {}),
        ("snapshots", {"porelo_version": "0.5.1~snapshot.600", "porelo_host_version": "0.5.1~snapshot.601"}),
    ],
    ids=["the releases' pins", "versions an inventory names"],
)
def test_pinned_versions_are_installed_exactly(channel, given):
    """Prevent a host taking another version than the release or the inventory names."""
    values = role_values(channel, **given)
    installs = program_installs(values)
    names = {name for names, state in installs for name in names}
    assert {"porelo=" + values["porelo_version"], "porelo-host=" + values["porelo_host_version"]} <= names
    assert not [names for names, state in installs if state == "latest"], "nothing named is upgraded past its pin"


def test_the_newest_versions_taken_are_named_on_a_note_line():
    """Prevent a host running snapshots nobody can name afterwards."""
    tasks = yaml.safe_load((ROOT / "roles/porelo/tasks/install.yml").read_text())
    notes = [task for task in tasks if "porelo_host_note" in task.get("tags", [])]
    assert len(notes) == 1
    values = role_values("snapshots")
    values["__porelo_package"] = {"stdout": "0.5.1~snapshot.612"}
    values["__porelo_host_package"] = {"stdout": "0.5.1~snapshot.613"}
    assert runs(notes[0], values)
    message = rendered(notes[0]["ansible.builtin.debug"]["msg"], values)
    assert "0.5.1~snapshot.612" in message and "0.5.1~snapshot.613" in message and "snapshots" in message
    assert not runs(notes[0], role_values("releases")), "a pinned host has nothing to say"


def test_the_newest_host_program_is_held_to_the_collections_floor():
    """Prevent a snapshots channel serving a host program older than the verbs the collection calls."""
    tasks = yaml.safe_load((ROOT / "roles/porelo/tasks/install.yml").read_text())
    compare = next(t for t in tasks if t.get("register") == "__porelo_host_version_comparison")
    values = role_values("snapshots")
    values["__porelo_host_package"] = {"stdout": "0.5.1~snapshot.613"}
    argv = [rendered(arg, values) for arg in compare["ansible.builtin.command"]["argv"]]
    assert argv[-1] == values["__porelo_host_floor"] == "0.5.1~snapshot.575", argv
