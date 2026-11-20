# HO199 — The Maven Cache Follows What The Build Resolved

```json
{ "$schema": "issue-1.json", "id": "HO199", "title": "The Maven Cache Follows What The Build Resolved", "state": "Review",
  "size": "S", "priority": "High", "rank": 1, "blockedBy": [],
  "covers": "Bug: the Build's Maven cache is keyed by build/pom.xml alone and saved only on a miss, so the build tools' versions that their snapshots move are fetched from Central on every Build until that pom changes." }
```

**Why this size.** The shared form copied: `pinned-jdk`, a new `maven-cache-save` action and the last step of three
jobs; no program and no contract another repository reads.

**What must be true.** A Build whose Maven cache was restored fetches from Central only what it has never fetched
before: once the shared build tools' snapshot or their parent moves, the next Build finds the new versions cached.

## Plan

- `pinned-jdk` restores `maven-<os>-<hashFiles(build/pom.xml)>-<run id>-<attempt>` by the prefixes
  `maven-<os>-<hashFiles>-`, then `maven-<os>-`, so no run hits exactly, and touches a marker after the restore.
- The new action `maven-cache-save` saves under that key only when a jar or pom changed status after the marker
  (`find -cnewer`: Maven dates a downloaded file by the server's Last-Modified, so its mtime says nothing).
- It is the last step, with `if: always()`, of the one job in each workflow that uses `pinned-jdk`: build.yml's
  build, shared-rules.yml's check and workflows.yml's check, each its own run.

## Acceptance

- Two Builds in a row with the same `build/pom.xml` and a build-tools snapshot that moved in between: the first saves
  a new entry, the second fetches no artifact from Central.
- With the new save step removed, the second Build fetches the moved versions again (seen once).

## To be checked

- The first two Builds after the push: the first logs "fetched after the restore" and saves, the second logs
  "nothing fetched after the restore" (the Maven call runs with `-q`, so this line is what shows it).
