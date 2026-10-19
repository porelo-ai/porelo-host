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
    def _message(result):
        if result._result.get("_ansible_no_log") or result._task.no_log:
            return HIDDEN
        return str(result._result.get("msg", ""))

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
            self._step(result, "ok", "failed and ignored: " + self._message(result))
        elif WAITING_TAG in result._task.tags:
            self._line(state="waiting", needs=self._needs(result))
        else:
            self._step(result, "failed", self._message(result))

    def v2_runner_on_unreachable(self, result):
        self._step(result, "failed", "unreachable: " + self._message(result))

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
