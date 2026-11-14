# HO191 — The Docs Say What The Code Does

```json
{
  "$schema": "issue-1.json",
  "id": "HO191",
  "title": "The Docs Say What The Code Does",
  "state": "Review",
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

## As built

A Sonnet sub-agent read ten pages of 34defd5 and checked about 320 claims against the code. It reported 19 findings.
I checked each one in the code and confirmed 18. `PORELO_HOST_MOLECULE_TRANSPORT` does exist, in the Molecule
scenario's `org_standin.yml`. I found two more while checking: README's account of `up` and the forge page's claim that
`down` stops tasks. Both 20 are fixed in the documents, and the code was right each time, so no bug is filed:

- **Removed programs still named.** `porelo-host-stop`, `porelo-host-push`, `porelo-host-person`,
  `porelo-host-project` and `porelo-host-forge-token` are removed by `legacy_programs.yml`. The pages now name the
  packaged `porelo-host task start|show|sweep`, `forge issue-token|lend-token` and `project give-back-check|take-off`,
  as the sudo rules and units call them. `doc/lines.md` loses the removed stop and push commands. `doc/ssh.md` names
  the host program's follow in place of the removed Python helper's methods.
- **What `up` runs.** Since [HO42](README.md#ho42), `up` prepares the host with no project and no person. It runs no `porelo setup`,
  no vault status, no forge request part, no project part and no agents part, and no role adds a need for the
  waiting stop. `doc/index.md`, `doc/lines.md` and the README now say so.
- **What `down` does.** It copies nothing off, and it stops no task itself: it refuses while a membership remains, and
  a purge stops that person's tasks. It checks before it pauses the follow, then checks again.
- **Numbers and names.** The README now gives the pins Porelo 0.5.0 and host program 0.5.1. The changelog has seven
  sudo rules, not six, and no longer has an entry for the token wrapper this release removes. The Molecule VM is
  6 GiB. `porelo_host_forge_agents` and its agent accounts, removed in 0.5.12, are gone from `doc/local-forge.md`.

Also seen but left as it is: `up.yml`'s waiting stop task stays, though nothing in the collection fills
`porelo_host_needs` now. It changes no behavior, so the documents describe it as it stands.
