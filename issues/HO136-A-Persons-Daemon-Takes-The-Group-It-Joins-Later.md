# HO136 — A Person's Daemon Takes The Group It Joins Later

**Status:** Accepted (operator, 2026-11-06).
**Kind:** Bug.
**Size:** S - the follow's group change followed by the person's user manager restarted where it is safe, with unit
tests and a Molecule step.

**What must be true.** A person who joins `porelo-people` after admission, by becoming a member of a project carried
on the host, can open the Matrix gate's socket from their `porelod` without a login anew and without root's hand.
Where a task of theirs runs, the restart waits, and `org status` names the person whose daemon still lacks the group.

## Why

On the rehearsal's host (operator, 2026-11-06), the host admin was admitted while porelo-ai's host card carried no
project, so `people_group` in `roles/porelo/files/porelo-host-person` left the person out of `porelo-people`, and
`start_daemon` started their user manager and `porelod` for good. Carrying porelo then added the person to the group,
but a running process keeps the groups it started with. The first task start, run by `porelod`, failed at
`/run/porelo-matrix/client.sock`: Permission denied. Root restarting `user@<uid>.service` fixed it.

## Plan

- **After a person joins `porelo-people`:** if none of the person's tasks runs, the follow restarts
  `user@<uid>.service` and waits for `porelod` as `start_daemon` does. If a task runs, it keeps it, and the person's
  status says `porelod` lacks the group until their tasks end; the next follow with none running restarts it.
- **Leaving the group** at a lock already ends the person's sessions; no change.
- **Red first:** a unit test of the follow admitting a person with no project, then carrying a project of theirs,
  expecting the manager's restart; today none comes.
- **Molecule:** the follow act admits a person before their project is carried, then carries it, and opens the gate's
  socket as that person from a process of their user manager.

## Acceptance

- The unit tests, seen red on today's follow and green after; the Molecule scenario green with the new step.
- A person admitted before their project is carried starts a task that joins the project's Matrix conversation.

## To be checked

- Whether the window's long-lived ssh session needs the group too; the task start goes through `porelod`, so it does
  not today.
