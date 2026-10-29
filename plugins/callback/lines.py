# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""One JSON line per task on stdout, for a program that runs the collection's playbooks."""

from __future__ import annotations

DOCUMENTATION = r"""
name: lines
type: stdout
short_description: One JSON line per task, for porelo-frontend's host command
description:
  - Writes one JSON object per line to stdout instead of Ansible's text, so a program reads each step's state.
  - A task's start gives C(started); its end gives C(ok), C(changed), C(skipped) or C(failed). A handler's lines are
    a task's; a meta task writes none, since Ansible ends it with no result.
  - A task's own C(vars.porelo_host_step) adds its string C(text) and non-negative integer C(seconds) to C(started),
    as written, without templating. A boolean is no duration; invalid seconds are omitted, invalid text omits both.
  - Before the first task, one C(plan) line lists the described steps of all plays in order, with their task names.
    Its C(steps) entries carry C(task), C(text) and optional C(seconds); C(task) matches the C(started) line's name.
    Conditions use the run's inventory, play, task and extra variables; false steps are omitted. A condition Ansible
    cannot decide yet leaves the step listed with C(when=true).
  - A reader skips a C(state) it does not know, as it skips a field. Added states and fields keep version 1.
  - A failed task tagged C(porelo_host_waiting) gives C(waiting) with the C(needs) its message names, the stop where
    the person's step comes.
  - A failed line's C(msg) includes command stderr, else stdout, with failed loop items labeled and output bounded.
  - A task with C(no_log) never has its message written.
requirements:
  - Set as the stdout callback, C(ANSIBLE_STDOUT_CALLBACK=porelo.host.lines).
"""

import json
import sys
from collections.abc import Mapping

from ansible.errors import AnsibleError
from ansible.plugins.callback import CallbackBase
from ansible.template import Templar

VERSION = 1
WAITING_TAG = "porelo_host_waiting"
# The task whose message is the host's values for a project's access file, which the interface reads from its own line.
HOST_TAG = "porelo_host_summary"
HIDDEN = "hidden, the task has no_log"
META_ACTIONS = ("meta", "ansible.builtin.meta", "ansible.legacy.meta")


class CallbackModule(CallbackBase):
    """Writes the run as JSON lines."""

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "stdout"
    CALLBACK_NAME = "porelo.host.lines"

    def __init__(self):
        super().__init__()
        self._play = ""
        self._playbook = None
        self._planned = False

    def _line(self, **fields):
        sys.stdout.write(json.dumps({"v": VERSION, **fields}, sort_keys=True) + "\n")
        sys.stdout.flush()

    def _step(self, result, state, msg=""):
        # The task's own name, as its start line has it: result.task_name drops a role's prefix on some ansible-core.
        self._line(play=self._play, task=result._task.get_name().strip(), state=state, msg=msg)

    @staticmethod
    def _words(data):
        words = str(data.get("stderr") or "").strip() or str(data.get("stdout") or "").strip()
        return "…" + words[-1000:] if len(words) > 1000 else words

    @staticmethod
    def _failed(item):
        # A loop's item result carries no failed key: failed_when's own answer, else its rc or an exception it raised.
        if "failed_when_result" in item:
            return bool(item["failed_when_result"])
        return bool(item.get("failed")) or item.get("rc", 0) != 0 or "exception" in item

    @classmethod
    def _message(cls, result, prefix=""):
        data = result._result
        if result._task.no_log or data.get("_ansible_no_log") or "censored" in data:
            return prefix + HIDDEN
        msg = prefix + str(data.get("msg", ""))
        items = data.get("results")
        if not isinstance(items, list):
            words = cls._words(data)
            if words and (words not in msg or len(msg) > 4000):
                remaining = 4000 - len(words) - 2
                if len(msg) > remaining:
                    msg = msg[: remaining - 1] + "…"
                return msg + ": " + words
            return msg if len(msg) <= 4000 else msg[:3999] + "…"

        details = []
        for item in items:
            # Hidden items must be handled before failure detection to avoid reading their details.
            if item.get("_ansible_no_log") or "censored" in item:
                details.append("an item hidden, it has no_log")
            elif cls._failed(item):
                words = cls._words(item) or str(item.get("msg", ""))
                label = str(item.get("_ansible_item_label", "an item"))
                if len(label) > 500:
                    label = label[:499] + "…"
                remaining = 1000 - len(label) - 2
                if len(words) > remaining:
                    words = "…" + words[-(remaining - 1) :]
                details.append(label + ": " + words)
        count = len(details)
        while True:
            dropped = count - len(details)
            suffix = [f"and {dropped} more items failed"] if dropped else []
            tail = "; ".join(details + suffix)
            message = msg + (": " + tail if tail else "")
            if len(message) <= 4000:
                return message
            if details:
                details.pop()
            elif tail:
                return msg[: 4000 - len(tail) - 4] + "…: " + tail
            else:
                return msg[:3999] + "…"

    @staticmethod
    def _description(task):
        """Reads only the task's own untemplated step fields."""
        step = task.vars.get("porelo_host_step")
        if not isinstance(step, Mapping) or not isinstance(step.get("text"), str):
            return {}
        fields = {"text": step["text"]}
        seconds = step.get("seconds")
        if isinstance(seconds, int) and not isinstance(seconds, bool) and seconds >= 0:
            fields["seconds"] = seconds
        return fields

    @staticmethod
    def _included(play, task):
        """Decides a step's conditions with the variables available before the run."""
        manager = play.get_variable_manager()
        loader = play.get_loader()
        templar = Templar(loader=loader, variables=manager.get_vars(play=play))
        hosts = manager._inventory.get_hosts(templar.template(play.hosts), ignore_restrictions=True)
        for host in hosts:
            templar = Templar(loader=loader, variables=manager.get_vars(play=play, host=host, task=task))
            if all(templar.evaluate_conditional(condition) for condition in task.when):
                return True
        return False

    def _plan(self):
        """Lists described tasks across every play before any task starts."""
        steps = []
        described = False
        for play in self._playbook.get_plays():
            for block in play.pre_tasks + play.tasks + play.post_tasks:
                for task in block.get_tasks():
                    fields = self._description(task)
                    if not fields or task.action in META_ACTIONS:
                        continue
                    described = True
                    try:
                        if not self._included(play, task):
                            continue
                    except AnsibleError:
                        # A later task may supply a condition's value, so the plan must not promise its omission.
                        fields["when"] = True
                    steps.append({"task": task.get_name().strip(), **fields})
        if described:
            self._line(state="plan", steps=steps)

    def v2_playbook_on_start(self, playbook):
        self._playbook = playbook
        self._planned = False

    def v2_playbook_on_play_start(self, play):
        self._play = play.get_name().strip()
        if not self._planned:
            self._plan()
            self._planned = True

    def v2_playbook_on_task_start(self, task, is_conditional):
        # Ansible gives a meta task such as flush_handlers no result, so its start would stand without an end.
        if task.action in META_ACTIONS:
            return
        self._line(play=self._play, task=task.get_name().strip(), state="started", msg="", **self._description(task))

    def v2_playbook_on_handler_task_start(self, task):
        self.v2_playbook_on_task_start(task, False)

    def v2_runner_on_ok(self, result):
        self._step(result, "changed" if result._result.get("changed") else "ok")
        if HOST_TAG in result._task.tags and isinstance(result._result.get("msg"), dict):
            self._line(state="host", host=result._result["msg"])

    def v2_runner_on_skipped(self, result):
        self._step(result, "skipped")

    def v2_runner_on_failed(self, result, ignore_errors=False):
        if ignore_errors:
            self._step(result, "ok", self._message(result, "failed and ignored: "))
        elif WAITING_TAG in result._task.tags:
            self._line(state="waiting", needs=self._needs(result))
        else:
            self._step(result, "failed", self._message(result))

    def v2_runner_on_unreachable(self, result):
        self._step(result, "failed", self._message(result, "unreachable: "))

    @staticmethod
    def _needs(result):
        # The stop's message is the list it waits for, as JSON; anything else is not a stop this callback can name.
        try:
            needs = json.loads(result._result.get("msg", ""))
        except (TypeError, ValueError):
            return ["unknown"]
        if isinstance(needs, list) and all(isinstance(need, str) for need in needs):
            return needs
        return ["unknown"]
