"""The forge's stops in a bring are waits the interface opens a stop for, read from the role's task files."""

import json
from pathlib import Path

import pytest
import yaml

TASKS = Path(__file__).parents[3] / "roles/forge/tasks"


def tasks(name):
    """Every task of a task file, those inside a block too."""
    found = []
    for task in yaml.safe_load((TASKS / name).read_text()):
        found.append(task)
        found.extend(tasks_in(task))
    return found


def tasks_in(task):
    inner = []
    for key in ("block", "rescue", "always"):
        for child in task.get(key, []):
            inner.append(child)
            inner.extend(tasks_in(child))
    return inner


@pytest.mark.parametrize(
    "name, task, needs",
    [
        (
            "repositories.yml",
            "repositories | Wait for the stop that gives the person's token while a repository is to migrate",
            ["forge-central-token"],
        ),
    ],
)
def test_a_forge_stop_is_a_tagged_failure_whose_message_is_its_needs(name, task, needs):
    stop = next(t for t in tasks(name) if t.get("name") == task)
    assert "porelo_host_waiting" in stop.get("tags", [])
    assert "when" in stop
    msg = stop["ansible.builtin.fail"]["msg"]
    assert json.loads(msg.replace("{{ ", "").replace(" | to_json }}", "").replace("'", '"')) == needs


def test_the_person_s_forge_token_comes_from_the_host_into_their_vault_with_no_stop():
    """Prevent a bring waiting at a stop for a lasting token, or the token reaching the play's file but not the vault."""
    assert not any("ansible.builtin.fail" in t for t in tasks("own.yml")), "own.yml has no stop left"
    take = next(t for t in tasks("own.yml") if t.get("name", "").startswith("own | Take the person's forge token"))
    cmd = take["ansible.builtin.shell"]["cmd"]
    assert "sudo -n /usr/local/sbin/porelo-host-person forge-token" in cmd
    assert cmd.index("porelo vault put") < cmd.index("mv --"), "the vault holds it before the play's file does"
    assert take.get("no_log") is True, "the token never reaches a log"
    acting = next(t for t in tasks("own.yml") if take in t.get("block", []))
    # In always, so the file goes when any forge call fails too.
    assert [t.get("name") for t in acting["always"]] == [
        "own | Remove the person's forge token from the runtime directory"
    ]
    assert acting["always"][0]["ansible.builtin.file"] == {"path": "{{ __forge_token }}", "state": "absent"}


@pytest.mark.parametrize("name", ["own.yml", "repositories.yml"])
def test_no_forge_stop_in_a_bring_is_left_a_plain_assert_naming_porelo_host_stop(name):
    for task in tasks(name):
        assert "porelo-host-stop" not in str(task.get("ansible.builtin.assert", "")), task.get("name")


def test_no_central_token_lies_on_the_host_for_a_bring():
    """Prevent the bring from reading the central token from a file, or migrating with it, instead of the stop's pipe."""
    forge = TASKS.parent
    named = [
        path
        for path in [*forge.glob("tasks/*.yml"), *forge.glob("vars/*.yml"), *forge.glob("defaults/*.yml")]
        if "forge-central.token" in path.read_text() or "forge_central_token" in path.read_text()
    ]
    assert not named, f"a central token file is still named in: {named}"
    assert "repos/migrate" not in (forge / "tasks/repositories.yml").read_text()
    listing = next(
        t for t in tasks("repositories.yml") if t.get("name") == "repositories | List what is still to migrate"
    )
    assert "{{ forge_owner }}.migrate" in listing["ansible.builtin.copy"]["dest"]
    assert listing["ansible.builtin.copy"]["mode"] == "0600"
