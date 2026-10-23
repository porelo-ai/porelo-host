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
  - A failed task tagged C(porelo_host_waiting) gives C(waiting) with the C(needs) its message names, the stop where
    the person's step comes.
  - A failed line's C(msg) includes command stderr, else stdout, with failed loop items labeled and output bounded.
  - A task with C(no_log) never has its message written.
requirements:
  - Set as the stdout callback, C(ANSIBLE_STDOUT_CALLBACK=porelo.host.lines).
"""

import json
import sys

from ansible.plugins.callback import CallbackBase

VERSION = 1
WAITING_TAG = "porelo_host_waiting"
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

    def v2_playbook_on_play_start(self, play):
        self._play = play.get_name().strip()

    def v2_playbook_on_task_start(self, task, is_conditional):
        # Ansible gives a meta task such as flush_handlers no result, so its start would stand without an end.
        if task.action in META_ACTIONS:
            return
        self._line(play=self._play, task=task.get_name().strip(), state="started", msg="")

    def v2_playbook_on_handler_task_start(self, task):
        self.v2_playbook_on_task_start(task, False)

    def v2_runner_on_ok(self, result):
        self._step(result, "changed" if result._result.get("changed") else "ok")

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
