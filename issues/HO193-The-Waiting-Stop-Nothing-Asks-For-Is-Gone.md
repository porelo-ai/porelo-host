# HO193 — The Waiting Stop Nothing Asks For Is Gone

```json
{
  "$schema": "issue-1.json",
  "id": "HO193",
  "title": "The Waiting Stop Nothing Asks For Is Gone",
  "state": "Backlog",
  "size": "XS",
  "priority": "Low",
  "rank": 1,
  "blockedBy": [],
  "covers": "`up`'s waiting stop and `porelo_host_needs`, which nothing in the collection fills since HO42, are removed with what only they use, or the issue says why they must stay."
}
```

**Why this size.** one task of `up.yml`, the `porelo` role's `main.yml`, `setup.yml` and `needs.yml` that no playbook
includes, the lines callback's `waiting` state and its tests and documents; whether Porelo or the window still read a
`waiting` line is asked first.

**What must be true.** Nothing in the collection waits for a need nothing names; or what still needs it is written
down beside it.

## Found

[HO191](README.md#ho191)'s reading: since [HO42](README.md#ho42) `up` prepares the host with no project and no
person, and no role adds to `porelo_host_needs`, so the second play's first task never stops.

## Plan

- Ask Agent Frontend and Core whether anything reads a `waiting` line or calls `porelo host stop-secrets` for this host.
- If nothing does: remove the stop task, the role's `main.yml`, `setup.yml` and `needs.yml`, the callback's `waiting`
  state with its tests, and the stop's paragraph in `doc/lines.md`; raise the lines contract's `v` only if a reader
  depends on it.
- If something does: say what, in `doc/lines.md` and here, and close the issue.
