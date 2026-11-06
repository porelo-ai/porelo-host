# HO138 — The Move Check Reads Each Line Where It Stands

**Status:** Analyzed.
**Kind:** Bug.
**Size:** S - two lines of `build/move-check.sh` read anew, with their unit tests in `tests/unit/test_move_tools.py`.

**What must be true.** Each line of the move check reads the fact it names from the place that holds it, so it is
green when that fact holds, whatever else is configured.

## Why

On the rehearsal's host (operator, 2026-11-06), the sluice task's work was on the host's forge as `porelo/sluice`
and `porelo/sluice-2`, its pull request #2 merged with the Build green. Still:

- *its last push reached the forge* failed. The line took the push's commit from `porelo build status`, which
  answers nothing without a `builds:` block in the project file, and it assumed the branch `porelo/<task>`, while the
  gate's approve after an amend chose `porelo/sluice-2`.
- *the task is listed in the room's agent-card.json* failed. `porelo talk peers` never lists a project's own tasks, by
  design (porelo's project file, `mail.peers`), and `Agent Sluice` is the development machine's room name, not the
  host's. So the line could never pass anywhere (Agent Matrix, 2026-11-06).

## Plan

- **The push:** the task's forge branch from `porelo task status --json`, and that branch's head read from the host's
  forge through its git port with the person's own forge token, given on standard input to Git's credential helper
  and never on a command line. Green when the branch holds the task's last pushed commit.
- **The Build:** the build reader's verdict for that same branch, as today, and named as not configured where the
  project has no `builds:` block, instead of `nothing`.
- **The conversation:** the task joined the project's conversation, by `porelo task status` or a message the task
  sent into it in `porelo talk log`. The line names the task's account in the room, not the development machine's
  agent name. The waking message's line stays as it is, until the room's tunnel joins the two.
- **Red first:** unit tests with stand-ins for `porelo` and `git`: a branch other than `porelo/<task>`, no `builds:`
  block, and a task that joined its conversation. Each is red on today's script.

## Acceptance

- The unit tests, seen red on today's script and green after.
- On the rehearsal's host, the check's push and conversation lines green for the sluice task, with the build line
  naming the reader as not configured while the project has no `builds:` block.

## To be checked

- The exact field of `porelo task status --json` that names the task's forge branch and its last pushed commit, and
  what says the task joined its conversation; read from porelo before building.
