"""The lines callback, run by the real ansible-playbook: the contract porelo-frontend's host command reads."""

import json
import os
import subprocess
from pathlib import Path

import pytest

PLAYS = Path(__file__).parent / "plays"


def run(play, *, traceback=False, extra_vars=None, inventory="localhost,"):
    """Runs a play with the callback and returns its exit code and its stdout as parsed lines."""
    environment = dict(os.environ, ANSIBLE_STDOUT_CALLBACK="porelo.host.lines", ANSIBLE_NOCOLOR="1")
    if traceback:
        environment["ANSIBLE_DISPLAY_TRACEBACK"] = "always"
    command = ["ansible-playbook", "-i", str(inventory), str(PLAYS / play)]
    if extra_vars is not None:
        command.extend(["-e", json.dumps(extra_vars)])
    done = subprocess.run(
        command,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [json.loads(line) for line in done.stdout.splitlines()]
    return done.returncode, lines, done.stdout + done.stderr


# Wrong step fields can break the reader's duration calculation or disclose a templated value.
@pytest.fixture(scope="module")
def described_steps():
    code, lines, output = run("step-fields.yml", extra_vars={"step_secret": "planted-step-secret"})
    assert code == 0, f"the metadata play must complete: {output}"
    return lines, output


def test_a_started_line_carries_the_tasks_own_text_and_seconds(described_steps):
    lines, output = described_steps
    started = next(line for line in lines if line.get("task") == "Describe a step" and line["state"] == "started")
    assert started == {
        "v": 1,
        "play": "Step fields",
        "task": "Describe a step",
        "state": "started",
        "msg": "",
        "text": "Installing Porelo",
        "seconds": 90,
    }, f"the reader needs the step's words and duration: {output}"


def test_step_text_is_read_without_templating(described_steps):
    lines, output = described_steps
    started = next(line for line in lines if line.get("task") == "Keep raw text" and line["state"] == "started")
    assert started.get("text") == "{{ step_secret }}", "step words must stay as written in the playbook"
    assert "planted-step-secret" not in output, "the callback must never expand step words into secret values"


def test_bad_seconds_leave_the_valid_text_alone(described_steps):
    lines, _ = described_steps
    names = [
        "Reject negative seconds",
        "Reject boolean seconds",
        "Reject string seconds",
        "Reject decimal seconds",
        "Reject null seconds",
        "Omit missing seconds",
        "Keep raw seconds",
    ]
    for name in names:
        started = next(line for line in lines if line.get("task") == name and line["state"] == "started")
        assert started.get("text") == "A step", f"{name} must keep its valid words"
        assert "seconds" not in started, f"{name} must omit a duration it cannot use"


def test_zero_seconds_are_a_valid_duration(described_steps):
    lines, _ = described_steps
    started = next(line for line in lines if line.get("task") == "Allow zero seconds" and line["state"] == "started")
    assert started.get("seconds") == 0, "a step that usually takes no time must retain zero"


def test_missing_or_non_string_text_leaves_both_fields_out(described_steps):
    lines, _ = described_steps
    names = [
        "Reject missing text",
        "Reject numeric text",
        "Reject boolean text",
        "Reject null text",
        "Reject a nonmapping block",
    ]
    for name in names:
        started = next(line for line in lines if line.get("task") == name and line["state"] == "started")
        assert "text" not in started and "seconds" not in started, f"{name} must not invent step metadata"
    plan = next(line for line in lines if line["state"] == "plan")
    assert [step["task"] for step in plan["steps"]] == [
        "Describe a step",
        "Keep raw text",
        "Reject negative seconds",
        "Reject boolean seconds",
        "Reject string seconds",
        "Reject decimal seconds",
        "Reject null seconds",
        "Omit missing seconds",
        "Keep raw seconds",
        "Allow zero seconds",
    ], "only tasks with valid words must enter the plan, in task order"
    assert plan["steps"][1]["text"] == "{{ step_secret }}", "the plan must also leave step words untemplated"
    assert all("seconds" not in step for step in plan["steps"][2:-1]), "the plan must omit invalid durations too"


def test_a_task_without_its_own_block_keeps_its_started_line(described_steps):
    lines, _ = described_steps
    started = next(line for line in lines if line.get("task") == "Stay unchanged" and line["state"] == "started")
    assert started == {
        "v": 1,
        "play": "Step fields",
        "task": "Stay unchanged",
        "state": "started",
        "msg": "",
    }, "a block inherited from the play must not change an ordinary task's line"


# An incomplete or unconditional plan gives the reader the wrong remaining run and duration.
@pytest.mark.parametrize("enabled", [False, True])
def test_one_plan_precedes_the_steps_of_both_plays_and_obeys_when(enabled):
    code, lines, output = run(
        "step-plan.yml",
        extra_vars={"include_optional_step": enabled},
        inventory=PLAYS / "step-inventory.yml",
    )
    assert code == 0, f"both plays must complete so their actual steps can be compared: {output}"
    expected = [
        {"task": "Start the first play", "text": "Preparing the host", "seconds": 10},
        {"task": "Include a described role", "text": "Installing Porelo", "seconds": 90},
        {"task": "Start the second play", "text": "Finishing the host", "seconds": 20},
    ]
    if enabled:
        expected.append({"task": "Run the optional step", "text": "Starting the forge", "seconds": 30})
    plans = [line for line in lines if line["state"] == "plan"]
    assert plans == [{"v": 1, "state": "plan", "steps": expected}], "one plan must name both plays' enabled steps"
    assert lines[0] == plans[0], "the reader needs the whole plan before the first task starts"
    starts = {line["task"]: line for line in lines if line["state"] == "started"}
    for step in expected:
        assert {field: starts[step["task"]].get(field) for field in step} == step, "plan fields must match task starts"
    completed = [
        line["task"] for line in lines if line["state"] == "ok" and line["task"] != "step_probe : Do inner work"
    ]
    assert completed == [step["task"] for step in expected], "planned task names must match the actual run"
    skipped = [line["task"] for line in lines if line["state"] == "skipped"]
    assert skipped == ([] if enabled else ["Run the optional step"]), "the extra var must change actual execution"
    inner = next(
        line for line in lines if line.get("task") == "step_probe : Do inner work" and line["state"] == "started"
    )
    assert "text" not in inner and "seconds" not in inner, "a role's inner task must not inherit step fields"
    assert all(line["v"] == 1 for line in lines), "the plan and step fields extend version 1"


def test_a_run_without_described_steps_keeps_its_existing_lines():
    _, lines, output = run("steps.yml")
    assert not any(line["state"] == "plan" for line in lines), f"an undescribed run must keep its usual lines: {output}"


def test_a_run_with_only_disabled_steps_still_gives_its_empty_plan():
    code, lines, output = run("step-disabled.yml")
    assert code == 0, f"skipping every described step must still complete: {output}"
    assert lines[0] == {"v": 1, "state": "plan", "steps": []}, "the reader must see that no described step will run"
    assert [line["state"] for line in lines] == ["plan", "started", "skipped"], "a false step must actually be skipped"


# A condition supplied later cannot be promised absent before its value exists.
def test_a_step_with_a_condition_supplied_later_is_marked_in_the_plan():
    code, lines, output = run("step-later-condition.yml")
    assert code == 0, f"the later value must allow the step to complete: {output}"
    assert lines[0] == {
        "v": 1,
        "state": "plan",
        "steps": [{"task": "Use the later value", "text": "Finishing the host", "seconds": 10, "when": True}],
    }, "the reader must know that the step's condition is unresolved at the start"
    assert lines[-1]["state"] == "ok", "the unresolved condition must be decided by Ansible when the task runs"


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
    code, _, output = run("steps.yml", traceback=True)
    assert code != 0, "the play's last task fails, so the run must fail"
    assert "planted-secret-value" not in output, f"the no_log task's message leaked: {output}"


def test_the_stop_is_a_waiting_line_naming_what_it_waits_for():
    code, lines, output = run("waiting.yml")
    assert code == 2, f"ansible-playbook ends a failed play with 2, and the caller maps it: {output}"
    assert {"v": 1, "state": "waiting", "needs": ["drive", "vault-new"]} in lines, output
    assert not [line for line in lines if line["state"] == "failed"], f"the stop is no failure: {output}"


def test_a_meta_task_writes_no_line_since_ansible_ends_it_with_none():
    _, lines, output = run("meta.yml")
    tasks = [(line["task"], line["state"]) for line in lines]
    assert tasks == [
        ("Change something and notify", "started"),
        ("Change something and notify", "changed"),
        ("Run the handler", "started"),
        ("Run the handler", "ok"),
        ("Do nothing after", "started"),
        ("Do nothing after", "ok"),
    ], output


# Missing refusal details prevent the caller from diagnosing a failed repository operation.
def test_a_failed_loop_reports_the_commands_reason_and_item_label():
    code, lines, _ = run("failed-loop.yml")
    assert code == 2, "the failing loop must stop the play"
    failed = [line for line in lines if line["state"] == "failed"]
    assert len(failed) == 1, "one loop must produce one failed task line"
    assert "planted-loop-reason" in failed[0]["msg"], "the command's refusal must reach the caller"
    assert "label-repository" in failed[0]["msg"], "the caller must know which item failed"


# Commands that explain a refusal on stdout must still be diagnosable.
def test_a_failed_command_reports_its_stdout_reason():
    code, lines, _ = run("failed-stdout.yml")
    assert code == 2, "the failing command must stop the play"
    failed = [line for line in lines if line["state"] == "failed"]
    assert len(failed) == 1, "one command must produce one failed task line"
    assert "planted-stdout-reason" in failed[0]["msg"], "stdout must supply the refusal when stderr is empty"


# Unbounded command output can flood the caller while discarding the final refusal hides its cause.
def test_a_long_failure_preserves_its_tail_within_the_message_cap():
    code, lines, _ = run("failed-tail.yml")
    assert code == 2, "the failing command must stop the play"
    failed = [line for line in lines if line["state"] == "failed"]
    assert len(failed) == 1, "one command must produce one failed task line"
    assert "planted-tail-reason" in failed[0]["msg"], "the final refusal must survive truncation"
    assert "…" in failed[0]["msg"], "discarded command output must be marked"
    assert len(failed[0]["msg"]) <= 4000, "the caller must receive a bounded message"


# A loop must never disclose output protected by task-level no_log.
def test_a_hidden_loop_never_discloses_its_output():
    code, lines, output = run("failed-hidden-loop.yml", traceback=True)
    assert code == 2, "the hidden command must still fail"
    assert "planted-loop-secret" not in output, "the hidden loop must not disclose its output"
    failed = [line for line in lines if line["state"] == "failed"]
    assert len(failed) == 1, "the hidden loop must retain its failed line"
    assert "hidden" in failed[0]["msg"], "the caller must see that details were hidden"


# One hidden item must not leak through the aggregate loop result.
def test_a_hidden_loop_item_never_discloses_its_output():
    code, lines, output = run("failed-hidden-item.yml", traceback=True)
    assert code == 2, "the hidden item must still fail"
    assert "planted-loop-secret" not in output, "the hidden item must not disclose its output"
    failed = [line for line in lines if line["state"] == "failed"]
    assert len(failed) == 1, "the loop must retain its failed line"
    assert "hidden" in failed[0]["msg"], "the caller must see that details were hidden"


# Many failed items must not flood the caller or silently conceal omitted failures.
def test_many_failed_items_report_how_many_were_dropped_within_the_cap():
    code, lines, _ = run("failed-many.yml")
    assert code == 2, "the failing loop must stop the play"
    failed = [line for line in lines if line["state"] == "failed"]
    assert len(failed) == 1, "one loop must produce one failed task line"
    msg = failed[0]["msg"]
    assert "planted-tail-reason" in msg, "the displayed items must carry their command's reason"
    assert len(msg) <= 4000, "the caller must receive a bounded message"
    shown = sum(f"{label}:" in msg for label in ("one", "two", "three", "four", "five", "six", "seven", "eight"))
    assert 0 < shown < 8, "the cap must retain some items and omit others"
    assert msg.endswith(f"and {8 - shown} more items failed"), "the caller must know the number omitted"


# Treating an accepted nonzero exit as failed can stop work that the task explicitly permits.
def test_a_loop_respects_failed_when_for_each_item():
    code, lines, output = run("failed-when-loop.yml")
    assert code == 2, output
    failed = [line for line in lines if line["state"] == "failed"]
    assert len(failed) == 1, output
    msg = failed[0]["msg"]
    assert "rejected-exit-three" in msg, "the rejected item must be named"
    assert "planted-conditional-reason" in msg, "the rejected item's stderr must reach the caller"
    assert "accepted-exit-one" not in msg, "failed_when permits exit 1"


# An unbounded module message can flood the caller without any command output.
def test_a_single_module_failure_stays_within_the_message_cap():
    code, lines, output = run("failed-message.yml")
    assert code == 2, output
    failed = [line for line in lines if line["state"] == "failed"]
    assert len(failed) == 1, output
    assert 0 < len(failed[0]["msg"]) <= 4000, "module messages must be bounded"


# Cutting the final refusal can hide the cause of an unsuccessful command.
def test_a_single_stderr_tail_survives_within_the_message_cap():
    code, lines, output = run("failed-stderr-tail.yml")
    assert code == 2, output
    failed = [line for line in lines if line["state"] == "failed"]
    assert len(failed) == 1, output
    msg = failed[0]["msg"]
    assert "planted-stderr-reason" in msg, "the command's final refusal must survive"
    assert 0 < len(msg) <= 4000, "command messages must be bounded"


# With traceback enabled, a hidden module's exception can disclose its message through the callback.
def test_a_hidden_module_loop_never_discloses_its_message():
    code, lines, output = run("failed-hidden-fail-loop.yml", traceback=True)
    assert code == 2, output
    assert "planted-loop-fail" not in output, "a hidden module message must never leak, including exceptions"
    failed = [line for line in lines if line["state"] == "failed"]
    assert len(failed) == 1, output
    assert "hidden" in failed[0]["msg"], "the callback must explain that details were hidden"


# One oversized item must not discard the only diagnosis or flood the caller.
def test_a_huge_loop_label_and_message_retain_the_reason_within_the_entry_cap():
    code, lines, output = run("failed-large-entry.yml")
    assert code == 2, output
    failed = [line for line in lines if line["state"] == "failed"]
    assert len(failed) == 1, output
    msg = failed[0]["msg"]
    entry = msg.split(": ", 1)[-1]
    assert "label-" in entry, "the item must still have a label"
    assert "planted-entry-reason" in entry, "the only item's diagnosis must not be dropped"
    assert ": …" in entry, "discarded item words must have a leading ellipsis"
    assert len(entry) <= 1000, "each label and its words must fit the item cap"
    assert len(msg) <= 4000, "the complete message must remain bounded"
