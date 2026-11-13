"""Prevent the host's test mode being written where Porelo's host program cannot judge it, or staying after down."""

import getpass
import json
import os
import re
import stat
import subprocess
from pathlib import Path

import yaml

HERE = Path(__file__).parent
ROOT = HERE.parents[2]


def play(tmp_path, **given):
    """Run the role's real test-mode tasks with the file in tmp_path."""
    variables = {
        "__porelo_test_mode_path": str(tmp_path / "test-mode.json"),
        "__porelo_test_mode_owner": getpass.getuser(),
        **given,
    }
    return subprocess.run(
        ["ansible-playbook", "-i", "localhost,", str(HERE / "plays/test_mode.yml"), "-e", json.dumps(variables)],
        env=dict(os.environ, ANSIBLE_STDOUT_CALLBACK="porelo.host.lines", ANSIBLE_NOCOLOR="1"),
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_switch_is_written_as_the_contract_says_private_to_root_and_said_loudly(tmp_path):
    done = play(tmp_path, porelo_host_test_switches=["start-uncertified"], porelo_host_test_why="a measuring host")
    assert done.returncode == 0, done.stdout + done.stderr
    written = tmp_path / "test-mode.json"
    assert json.loads(written.read_text()) == {"v": 1, "switches": ["start-uncertified"], "why": "a measuring host"}
    assert stat.S_IMODE(written.stat().st_mode) == 0o600
    assert "TEST MODE" in done.stdout and "start-uncertified" in done.stdout, done.stdout


def test_no_switch_takes_the_file_away(tmp_path):
    written = tmp_path / "test-mode.json"
    written.write_text('{"v": 1, "switches": ["start-uncertified"], "why": "left"}')
    done = play(tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    assert not written.exists()
    assert "TEST MODE" not in done.stdout


def test_a_switch_nobody_knows_is_refused_and_nothing_is_written(tmp_path):
    bad = (
        ["start-uncertified", "everything-off"],
        "start-uncertified",
        [True],
        {"a": 1},
        None,
        [["start-uncertified"]],
        [""],
    )
    for switches in bad:
        done = play(tmp_path, porelo_host_test_switches=switches)
        assert done.returncode != 0, switches
        assert not (tmp_path / "test-mode.json").exists(), switches


def test_a_link_where_the_file_goes_is_replaced_and_not_written_through(tmp_path):
    aim = tmp_path / "elsewhere"
    aim.write_text("kept")
    (tmp_path / "test-mode.json").symlink_to(aim)
    done = play(tmp_path, porelo_host_test_switches=["start-uncertified"])
    assert done.returncode == 0, done.stdout + done.stderr
    assert aim.read_text() == "kept"
    assert not (tmp_path / "test-mode.json").is_symlink()


def test_down_takes_the_test_mode_away_first_and_plainly_and_the_people_may_ask_for_the_switches():
    first = {"path": "/etc/porelo-host/test-mode.json", "state": "absent"}
    role = yaml.safe_load((ROOT / "roles/porelo/tasks/down.yml").read_text())
    assert role[0].get("ansible.builtin.file") == first, role[0]
    tasks = yaml.safe_load((ROOT / "playbooks/down.yml").read_text())[0]["tasks"]
    checks = next(i for i, task in enumerate(tasks) if "block" in task)
    assert any(task.get("ansible.builtin.file") == first for task in tasks[:checks]), "before any check may refuse"
    rules = (ROOT / "roles/porelo/templates/porelo-host-person.sudoers.j2").read_text()
    assert re.search(r"(?m)^%porelo-people ALL=\(root\) NOPASSWD: /usr/sbin/porelo-host test-switches --json$", rules)


def test_the_only_known_switch_is_the_one_core_reads():
    specs = yaml.safe_load((ROOT / "roles/porelo/meta/argument_specs.yml").read_text())
    option = specs["argument_specs"]["person"]["options"]["porelo_host_test_switches"]
    assert option["default"] == [] and option["elements"] == "str"
    assert option["choices"] == ["start-uncertified"]
