# HO90 — Each Person's State Named By Sync And Status

**Status:** Idea.
**Severity:** medium - the interface cannot confirm an added developer or offer Lock and Unlock from what the host
answers, and `registry status` names some persons in a state they are not in.
**Size:** S - one helper's two answers and their unit tests, no contract another repository reads beyond the answers'
new fields.

**What must be true.** Whoever runs `sync <project>` or `registry status` on the host reads each person's state as it
is, with no window in which it is named wrongly:

- `sync <project>` answers, beside `added`, `dropped` and `refused`, each person of the project with their state
  (`active`, `locked`, `pending`, `purged` or `named`), in the words `registry status` uses;
- `registry status` leaves out a login the registry names revoked and one the host refuses, instead of answering it
  `named`;
- a purge cut off between recording `purged` and removing the person's record answers `pending`, not `locked` or
  `active`;
- a person with no membership left, in the window of a project's removal before their lock, answers `pending`, not
  `active`.

## Acceptance

- A unit test for each bullet, seen red first: sync's answer with an added, a locked and a pending person; a revoked
  and a refused login absent from status; a purge cut off after `purged`; a project's removal stopped before the lock.
