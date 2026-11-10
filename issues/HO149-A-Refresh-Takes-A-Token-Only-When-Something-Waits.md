# HO149 — A Refresh Takes A Token Only When Something Waits

```json
{
  "$schema": "issue-1.json",
  "id": "HO149",
  "title": "A Refresh Takes A Token Only When Something Waits",
  "state": "Idea",
  "size": "XS",
  "priority": "Medium",
  "rank": 4,
  "blockedBy": [],
  "covers": "*Refresh* takes the host admin's central token only while a project, a repository or a take-off waits for one, on a host with a forge of its own as on one without, and otherwise refuses it the same way on both."
}
```

**Why this size.** one condition in `porelo-host-person refresh`, its tests, and a line in `doc/` where *Refresh* is described.

**What must be true.** *Refresh* (`porelo-host-person org refresh`) takes the host admin's central token only while
something on the host waits for one, on a host with a forge of its own as on one without:
- a project in `waiting-for-token`;
- a repository that "waits for a central token";
- a repository to be taken off that is held.

Otherwise it refuses the token with the same message on both kinds of host, and changes nothing. A refresh with an
empty input follows as before.

## Why

The rule from [HO94](README.md#ho94) and [HO96](README.md#ho96) is that a token is taken only while it is needed, so
none is handed over for nothing. Today it holds on a host without a forge of its own: a token there with no project
waiting is refused with "no project waits for a token; org refresh requires empty standard input". On a host with a
forge of its own, the check is switched off. There, single repositories of a carried project can wait for a token while
the project itself does not, and "does a project wait?" was too narrow for that. So such a host takes any token, and the
run uses it for nothing when nothing waits. The admin sees no error and cannot tell whether the token was needed.

## The shape

- `refresh` asks one question on both kinds of host: does a project wait, does a repository wait for a central token,
  or is a take-off held? A token is taken only when one of them holds. The first token, which adds the organization's
  read key, is taken as today.
- The refusal stays exit 65, with a message naming what would have needed a token: "nothing on this host waits for a
  token; org refresh requires empty standard input".
- Tests, seen red first:
  - On a forge host, a token with nothing waiting is refused. Today it is taken.
  - On a forge host, a token with only a repository waiting is taken.
  - A held take-off takes it.
  - A host without a forge refuses as before.
  - `org status` names what waits, so the admin knows before giving one.
