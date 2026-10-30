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
            "own.yml",
            "own | Wait for the stop that gives the person's forge token while the vault holds none",
            ["identities"],
        ),
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
