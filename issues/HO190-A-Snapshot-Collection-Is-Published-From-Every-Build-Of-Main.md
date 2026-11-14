# HO190 — A Snapshot Collection Is Published From Every Build Of Main

```json
{
  "$schema": "issue-1.json",
  "id": "HO190",
  "title": "A Snapshot Collection Is Published From Every Build Of Main",
  "state": "Review",
  "size": "S",
  "priority": "Highest",
  "rank": 1,
  "blockedBy": [],
  "covers": "Every push to `main` that builds publishes the collection as a snapshot, its SHA256SUMS and a `latest.json` pointer on the rolling `snapshot` pre-release, so a Porelo snapshot carries the newest collection and its `/usr/sbin/porelo-host`."
}
```

**Why this size.** one job pair in `build.yml`, a check of the published files with its unit tests, and the documents;
no role changes.

**What must be true.** Whatever Porelo snapshot is used, the collection it needs is there as a snapshot too: a build of
the window fetches the newest snapshot collection from one fixed place without a person, checked by its digest. A
machine set up from it has `/usr/sbin/porelo-host`, which `porelo org host refresh` calls; the release 0.5.12 has only
`porelo-host-person`, so its follow waits for the host admin's token for good.

## Plan

- **The place.** The rolling pre-release `snapshot` of this repository on GitHub:
  `https://github.com/porelo-ai/porelo-host/releases/download/snapshot/`. It needs no credential but the Build job's own
  token, and is the host the window's build already fetches releases from. The `v*` release tags stay the operator's.
- **The files.** `porelo-host-<galaxy version>.<run number>.tar.gz` (e.g. `porelo-host-0.5.13-snapshot.412.tar.gz`), a
  valid collection version that sorts by run number; `SHA256SUMS` with one line per tarball kept, the newest five; and
  `latest.json`, `{"version", "file", "sha256", "commit"}`, uploaded last so it never names a file that is not there.
- **The jobs**, in `release.yml`, whose `publish` is the one job `check-actions` lets write `contents`: on a push to
  `main` (the Build's own paths), `build` builds the tarball with the run's version, checks it with
  `build/check-tarball.sh`, writes `SHA256SUMS` and `latest.json` and checks them with `build/check-snapshot.py`,
  holding no token; `publish`, with no checkout, takes them by the artifact's id, creates the pre-release once,
  uploads in that order and removes tarballs no longer listed; `snapshot-check`, without a token, fetches all three
  anonymously and checks them again. A `v*` tag publishes its release as before. The Build checks the same commit
  beside it.
- **`build/check-snapshot.py <dir>`**, Python like `build/measure-tables.py`, since it reads JSON: `latest.json`'s
  fields well formed, its file present with that digest, and `SHA256SUMS` naming it exactly once with the same digest;
  a failure prints what it asked and what it got.
- **Red first:** `tests/unit/test_check_snapshot.py` over fixtures: a good directory passes; a pointer with another
  digest, a file that changed, a `SHA256SUMS` without the file or naming it twice, and a pointer that is no JSON each
  fail. Red while the script does not exist.
- **Documents:** the README says where the snapshot is; `AGENTS.md` names the script; a changelog entry.

## Acceptance

- After the push, Release's `snapshot-check` is green, and `latest.json` at the place names a file whose digest
  matches the file and `SHA256SUMS`, checked anonymously with `build/check-snapshot.py`.
- The unit tests, seen red without the script and green with it.
