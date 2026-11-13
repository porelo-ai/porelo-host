# HO90 — Each Person's State Named By Status

```json
{
  "$schema": "issue-1.json",
  "id": "HO90",
  "title": "Each Person's State Named By Status",
  "state": "Idea",
  "size": "S",
  "priority": "Low",
  "rank": 29,
  "blockedBy": [],
  "covers": "`org status` leaves out revoked and refused logins and names a cut-off purge or a removal's window `pending`."
}
```

**Why this size.** one helper's answer and its unit tests, no contract another repository reads beyond that answer.

**What must be true.** Whoever runs `org status` on the host reads each person's state as it is, with no window in which
it is named wrongly. Its severity is medium: the interface reads a person's state from `org status`, which names some
persons in a state they are not in. It answers each person's `state` today (`active`, `locked`, `pending`, `purged` or `named`), and
`org refresh` answers the same; both these still fail:

- `org status` leaves out a login the organization names revoked and one the host refuses, instead of answering it
  `named`;
- a purge cut off between recording `purged` and removing the person's record answers `pending`, not `locked` or
  `active`;
- a person with no membership left, in the window of a project's removal before their lock, answers `pending`, not
  `active`.

## Acceptance

- A unit test for each bullet, seen red first: a revoked and a refused login absent from status; a purge cut off after
  `purged`; a project's removal stopped before the lock.
