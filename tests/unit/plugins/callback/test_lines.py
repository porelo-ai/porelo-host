"""The lines callback, run by the real ansible-playbook: the contract porelo-frontend's host command reads."""

import json
import os
import subprocess
from pathlib import Path

PLAYS = Path(__file__).parent / "plays"


def run(play):
    """Runs a play with the callback and returns its exit code and its stdout as parsed lines."""
    environment = dict(os.environ, ANSIBLE_STDOUT_CALLBACK="porelo.host.lines", ANSIBLE_NOCOLOR="1")
    done = subprocess.run(
        ["ansible-playbook", "-i", "localhost,", str(PLAYS / play)],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [json.loads(line) for line in done.stdout.splitlines()]
    return done.returncode, lines, done.stdout + done.stderr


def test_every_line_is_json_of_the_contracts_version():
    _, lines, output = run("steps.yml")
    assert lines, f"no line at all in: {output}"
    assert all(line["v"] == 1 for line in lines), output


def test_each_task_starts_once_and_ends_in_its_own_state():
    _, lines, output = run("steps.yml")
    ends = [(line["task"], line["state"]) for line in lines if line["state"] != "started"]
    assert ends == [
        ("Do nothing", "ok"),
        ("Change something", "changed"),
        ("Be skipped", "skipped"),
        ("Fail and be ignored", "ok"),
        ("Fail with a secret", "failed"),
    ], output
    starts = [line["task"] for line in lines if line["state"] == "started"]
    assert starts == [task for task, _ in ends], output


def test_a_task_with_no_log_never_writes_its_message():
    code, _, output = run("steps.yml")
    assert code != 0, "the play's last task fails, so the run must fail"
    assert "planted-secret-value" not in output, f"the no_log task's message leaked: {output}"


def test_the_stop_is_a_waiting_line_naming_what_it_waits_for():
    code, lines, output = run("waiting.yml")
    assert code == 2, f"ansible-playbook ends a failed play with 2, and the caller maps it: {output}"
    assert {"v": 1, "state": "waiting", "needs": ["drive", "vault-new"]} in lines, output
    assert not [line for line in lines if line["state"] == "failed"], f"the stop is no failure: {output}"
