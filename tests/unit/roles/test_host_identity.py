"""Guard how a re-rented host takes the identity its preparation brought: through the host program alone."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def organization_tasks():
    return yaml.safe_load((ROOT / "roles/porelo/tasks/organization.yml").read_text())


def named(tasks, words):
    return next(index for index, task in enumerate(tasks) if words in task.get("name", ""))


def identity_block():
    return next(task for task in organization_tasks() if "block" in task and "identity" in task["name"])


def test_the_identity_is_imported_before_any_read_key_is_made_or_followed():
    """Prevent a re-rental from making a new organization read key, which would need a second deploy key."""
    tasks = organization_tasks()
    block = next(index for index, task in enumerate(tasks) if "block" in task and "identity" in task["name"])
    assert named(tasks, "private credential directories") < block < named(tasks, "Generate the organization's read key")
    assert block < named(tasks, "Enable the follow"), "the follow's timer starts only after the import"
    assert named(tasks, "Name the host to the helper") < block, "the host program refuses before forge.conf exists"
    person = yaml.safe_load((ROOT / "roles/porelo/tasks/person.yml").read_text())
    follow = next(
        index
        for index, task in enumerate(person)
        if task.get("ansible.builtin.command", {}).get("argv", [])[-2:] == ["org", "follow"]
    )
    assert named(person, "Configure the organization") < follow, "the first follow runs only after the import"


def test_the_identity_reaches_the_host_program_on_standard_input_alone():
    """Prevent key text from becoming an Ansible variable, a task's output or a command line."""
    block = identity_block()
    task = next(t for t in block["block"] if "ansible.builtin.shell" in t)
    cmd = task["ansible.builtin.shell"]["cmd"]
    assert cmd.startswith("env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin /usr/sbin/porelo-host identity import < ")
    assert "__porelo_identity_file" in cmd
    assert set(cmd.split("<")[1].split()) == {"{{", "__porelo_identity_file", "|", "quote", "}}"}, "only the path"
    assert task["changed_when"] == "__porelo_identity_import.stdout == 'imported'"
    assert task["notify"] == "Serve the host's own SSH host keys"
    for path in (ROOT / "roles").rglob("*.yml"):
        for line in path.read_text().splitlines():
            if "identity" in line:
                assert not any(reader in line for reader in ("slurp", "lookup(", "from_json")), (path, line)


def test_the_brought_identity_is_removed_whether_the_import_passed_or_not():
    """Prevent the identity's private keys from staying on the host's disk outside the host program's files."""
    block = identity_block()
    assert block["when"] == "__porelo_identity_stat.stat.exists"
    removal = block["always"][0]["ansible.builtin.file"]
    assert removal == {"path": "{{ __porelo_identity_file }}", "state": "absent"}


def test_only_a_file_of_roots_alone_is_imported_and_an_unsafe_one_is_removed_too():
    """Prevent another account from placing or reading the identity the host takes, or a refused file from staying."""
    block = identity_block()
    assert "assert" in str(block["block"][0]), "the check stands inside the block whose always removes the file"
    check = block["block"][0]["ansible.builtin.assert"]["that"]
    assert any("isreg" in line and "islnk" in line and "uid == 0" in line and "'0600'" in line for line in check)


def test_sshd_serves_the_imported_host_keys_before_the_play_goes_on():
    """Prevent a later failure from leaving a rerun whose import is unchanged and whose sshd serves old keys."""
    tasks = organization_tasks()
    block = next(index for index, task in enumerate(tasks) if "block" in task and "identity" in task["name"])
    assert tasks[block + 1].get("ansible.builtin.meta") == "flush_handlers"
    handlers = yaml.safe_load((ROOT / "roles/porelo/handlers/main.yml").read_text())
    handler = next(h for h in handlers if h["name"] == "Serve the host's own SSH host keys")
    assert handler["ansible.builtin.service"]["state"] == "reloaded"
