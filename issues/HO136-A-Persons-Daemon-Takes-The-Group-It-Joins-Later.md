# HO136 — A Person's Daemon Takes The Group It Joins Later

```json
{
  "$schema": "issue-1.json",
  "id": "HO136",
  "title": "A Person's Daemon Takes The Group It Joins Later",
  "state": "Review",
  "size": "S",
  "priority": "Medium",
  "rank": 18,
  "blockedBy": [],
  "covers": "Bug: a person who joins `porelo-people` after admission gets a `porelod` with that group, its user manager restarted where no task runs."
}
```

**Why this size.** the follow's group change followed by the person's user manager restarted where it is safe, with unit
tests and a Molecule step.

**What must be true.** A person who joins `porelo-people` after admission, by becoming a member of a project carried
on the host, can open the Matrix gate's socket from their `porelod` without a login anew and without root's hand.
Where a task of theirs runs, the restart waits, and `org status` names the person whose daemon still lacks the group. It is a bug.

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

## Done

- `people_group` checks every admitted person's running user manager by the `Groups:` line of its process. One without
  `porelo-people` is restarted with `porelod`, unless a container of the person runs (`pgrep -u <login> -x conmon`),
  a task's among them: then the follow says so on stderr and a later follow restarts it. A failed restart is said on
  stderr and the follow goes on. Admission joins the groups before `loginctl enable-linger` starts the manager.
- **Changed after review:** the first cut held the restart on a task certificate in force. That ended a task running
  past its certificate's end and kept a manager without the group after `task --end`; a running `conmon` is the
  person's work itself.
- Unit tests: a manager without the group restarted, one with it left running, one kept for a running container with
  the person told, one restarted though an ended task's certificate holds, a failed restart said with the follow going
  on, and admission's group before linger. Each was red on the code before it.
- **Not done as planned:** the person's status in `org status` names it on stderr of the follow only, in the journal for
  a timer's follow.
- The Molecule step checks every admitted person's manager for the group after the follow; the scenario admits its
  persons with their project already carried, so it shows the end state, not the late join.
