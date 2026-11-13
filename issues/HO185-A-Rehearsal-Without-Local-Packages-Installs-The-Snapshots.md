# HO185 — A Rehearsal Without Local Packages Installs The Snapshots

```json
{
  "$schema": "issue-1.json",
  "id": "HO185",
  "title": "A Rehearsal Without Local Packages Installs The Snapshots",
  "state": "Backlog",
  "size": "S",
  "priority": "Medium",
  "rank": 7,
  "blockedBy": [],
  "covers": "A rented rehearsal given no PORELO_HOST_DEB installs Porelo and porelo-host from the snapshots it names, instead of failing at up on a release version the snapshots channel does not hold."
}
```

**Why this size.** the rehearsal's inventory names the versions it installs, read from the channel, with the
rehearsal's own line for it; the roles stay as they are.

**What must be true.** `build/rehearse-move.sh rented` with no `PORELO_HOST_DEB` brings the host up from the signed
snapshots channel: its inventory names `porelo_host_distribution: snapshots`, and the versions installed are ones that
channel holds.

## Found

The story run on a local VM, 2026-11-13 (porelo-host ad4aca4): `up` failed at `porelo : install` with "no available
installation candidate for porelo=0.5.0". The rehearsal sets `porelo_host_distribution: snapshots`, but
`porelo_version` stays the role's default, the release `0.5.0`, and `porelo_host_version` a fixed `~snapshot.474`.
The run went on with snapshot 508's packages given as local ones.

## Plan

- Without local packages, the rehearsal reads the newest `porelo` and `porelo-host` of the snapshots channel from its
  signed index and names both versions in the inventory; it says which it took.
- Or it refuses at once, before ordering anything, naming `PORELO_HOST_DEB` as what it needs.

## Acceptance

- A rented rehearsal without `PORELO_HOST_DEB` passes `up` on a fresh local VM, or stops before `up` saying why.
