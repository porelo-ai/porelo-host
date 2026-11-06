# HO138 — The Move Check Reads Each Line Where It Stands

**Status:** Review.
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

## Done

- **Read from porelo:** `porelo task status --json` holds only `name`, `state`, `running`, `project`, `repository`,
  `parameters` and `usage`: no forge branch, no pushed commit, nothing on the conversation. The readable form holds
  `forge <branch>`, the branch the task's start settled, and one `build <commit> ...` line per push seen, the newest
  first, only where a build reader follows the task. The gate's approve takes `<branch>-2`, `-3`, ... when the branch
  holds earlier work, and records that choice nowhere `task status` shows. `porelo build status` exits 78 for a project
  without a `builds:` block, and for nothing else. In `porelo talk log`, a message the task sent and a transport took
  is a `sent` row whose detail names the transport, `matrix` for the project's conversation.
- **The push:** the newest `build` commit, found on the host's forge as the `forge` branch or `<branch>-<n>`, read by
  `git ls-remote` on `127.0.0.1:<git_port>` with `porelo vault credential --entry <forge name>.person` answering Git.
  The vault is read rather than `porelo-host-person forge-token` called, since that makes the person's one token anew
  and deletes the one their vault holds. Without a `builds:` block the line says `cannot say` and why.
- **The Build:** asked for the branch that holds the push, `not configured` on exit 78.
- **The conversation:** green on a `sent` row over `matrix` in `porelo talk log <task>`; `porelo task status` says
  nothing about the conversation.
- **Red first:** the new and changed unit tests, 10 of 28, failed on the script before the change; all 28 pass after.
- **Still open:** on a host without a `builds:` block the push line cannot be green until `porelo task status` names
  the task's last pushed commit and the branch the gate's approve chose; that is porelo's to add. The acceptance on the
  rehearsal's host is not run yet.
