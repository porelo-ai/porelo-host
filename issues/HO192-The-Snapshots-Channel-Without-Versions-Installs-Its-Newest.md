# HO192 — The Snapshots Channel Without Versions Installs Its Newest

```json
{
  "$schema": "issue-1.json",
  "id": "HO192",
  "title": "The Snapshots Channel Without Versions Installs Its Newest",
  "state": "Review",
  "size": "S",
  "priority": "Highest",
  "rank": 1,
  "blockedBy": [],
  "covers": "Bug: `up` with `porelo_host_distribution: snapshots` and no versions installs the newest `porelo` and `porelo-host` the snapshots channel's signed index holds and says which, instead of failing on the release pin `porelo=0.5.0`; releases stay pinned."
}
```

**Why this size.** the `porelo` role's two version defaults, its install tasks and a note line, with their unit tests
and one VM run of `up`; no other role changes.

**What must be true.** A host the window sets up from the snapshots channel, naming no versions, gets Porelo and its
host program, the newest that channel holds, and `up` names both versions on a note line. A host program older than
the one whose verbs the collection calls is still refused. Versions an inventory names are installed exactly, and the
releases channel keeps its pins.

## Found

The operator's live setup on the rented server, 2026-11-14 14:34 Berlin, from the window (porelo-frontend c54199a4)
with collection 0.5.13-snapshot.13: `up` failed at `porelo.host.porelo : install | Install Porelo from it` with "no
available installation candidate for porelo=0.5.0". The window names `porelo_host_distribution: snapshots` and no
version, so the role took its release defaults. [HO185](README.md#ho185) fixed this for the move rehearsal alone.

## Plan

- **Defaults.** On the snapshots channel `porelo_version` and `porelo_host_version` default to empty, meaning the
  newest; on the releases channel they keep `0.5.0` and `0.5.1~snapshot.474`.
- **Install.** Named versions are installed as now. Empty ones are installed by name with `state: latest` from the
  signed repository, after the index was refreshed, and the local-packages path takes the bare name too.
- **Floor.** The installed `porelo-host` is compared with the named version, or else with the oldest the collection
  works with, `0.5.1~snapshot.474`, kept in the role's vars.
- **Note.** A `porelo_host_note` line names the versions taken when any was the newest.
- **Red first:** unit tests over the defaults and the install tasks for both channels, red before the change.
- **Proof:** one VM run of `up` with `porelo_host_distribution: snapshots` and no versions.

## Acceptance

- The unit tests, seen red without the change and green with it.
- On a fresh VM, `up` with the snapshots channel and no versions passes the install and prints the note with both
  versions.

## As built

The plan as written. `__porelo_pinned_programs` and `__porelo_newest_programs` in the role's vars split Porelo's two
programs by whether a version is named. The newest are installed with `state: latest` after the pinned install
refreshed the index, and the local-packages path takes their bare names. `__porelo_host_floor` holds the host program
to `0.5.1~snapshot.474` when no version is named. The wiring test now reads that floor instead of the old default.

Red first: `test_the_snapshots_channel_without_versions_installs_its_newest` failed with
`porelo=0.5.0` on the snapshots channel before the change. The note and floor tests failed too, and the pinned tests
passed before and after.

On a fresh local VM (Ubuntu 26.04, 2026-11-14), the collection built from this commit was installed, and
`porelo.host.up` ran with an inventory naming only its version, `alpha`, network 7 and
`porelo_host_distribution: snapshots`. The install passed: Porelo installed, the newest installed, the floor held. The
note line read "No version named for porelo and porelo-host: took the newest of the snapshots channel. Installed porelo
0.5.1~snapshot.540 and porelo-host 0.5.1~snapshot.540." `up` stopped afterwards at the machine file the window uploads,
which this VM was not given.
