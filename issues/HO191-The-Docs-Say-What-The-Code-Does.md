# HO191 — The Docs Say What The Code Does

```json
{
  "$schema": "issue-1.json",
  "id": "HO191",
  "title": "The Docs Say What The Code Does",
  "state": "Implementing",
  "size": "M",
  "priority": "Highest",
  "rank": 1,
  "blockedBy": [],
  "covers": "Every sentence of the README, `doc/` but its decisions' history, and the changelog's latest section that names a command, flag, path, default, state, message or behavior is borne out by the code on `main`, or a bug is filed for the code."
}
```

**Why this size.** About 1,300 lines of user-facing text over nine pages, the forge's page alone 540, each claim read
against the roles, scripts and workflows it names; no behavior changes.

**What must be true.** A reader who follows the documents finds the commands, flags, paths, defaults, states and
messages they name. Where the document is wrong it says what the code does; where the code is wrong a bug stands in the
backlog, and the document is left as it is.

## Plan

- **The reading.** A Claude sub-agent on Sonnet (`claude-sonnet-5-5`) reads `README.md`, `doc/*.md` but
  `doc/decisions.md`, and the changelog's latest section page by page against the code on `main`, and lists each
  sentence the code does not bear out: the claim at file:line and the code at file:line that contradicts it. It runs no
  test suite and no VM.
- **The check.** Each finding is checked in the code by the lane, not the sub-agent; only a confirmed one is changed.
- **The change.** The document is corrected where the code is right; where the code is wrong, its own bug goes to the
  backlog, estimated.

## Acceptance

- One commit; the document tests, `check-commits`, `check-citations` and the local traces check green.
- The Push ready names the count: claims checked, confirmed, fixed, filed as bugs.
