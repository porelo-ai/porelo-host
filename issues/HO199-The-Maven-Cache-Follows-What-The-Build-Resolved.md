# HO199 — The Maven Cache Follows What The Build Resolved

```json
{ "$schema": "issue-1.json", "id": "HO199", "title": "The Maven Cache Follows What The Build Resolved", "state": "Backlog",
  "size": "S", "priority": "High", "rank": 1, "blockedBy": [],
  "covers": "Bug: the Build's Maven cache is keyed by build/pom.xml alone and saved only on a miss, so the build tools' versions that their snapshots move are fetched from Central on every Build until that pom changes." }
```

**Why this size.** One composite action, `pinned-jdk`, and its cache steps; no program and no contract another
repository reads.

**What must be true.** A Build whose Maven cache was restored fetches from Central only what it has never fetched
before: once the shared build tools' snapshot or their parent moves, the next Build finds the new versions cached.

## Plan

- Today `pinned-jdk` uses `actions/cache` with the key `maven-<os>-<hashFiles(build/pom.xml)>`, which saves nothing
  after an exact hit. `build/pom.xml` names the build tools as a snapshot whose dependencies and parent move while
  that pom does not, so whatever a move adds is fetched by every Build and never kept.
- Restore and save become separate steps: the save also runs after an exact hit when the job wrote any file into the
  repository after the restore, under the key with the run's id appended, and the restore takes the newest entry by
  its prefix; older entries of the prefix are deleted by the Build, as porelo-buildtools' prune job does.
- The `-q` Maven call says what it fetched (`-B -ntp` without `-q`, or a count of files written after the restore),
  so a Build log shows downloads after a hit.

## Acceptance

- Two Builds in a row with the same `build/pom.xml` and a build-tools snapshot that moved in between: the first saves
  a new entry, the second fetches no artifact from Central.
- With the new save step removed, the second Build fetches the moved versions again (seen once).

## To be checked

- Not measured yet: the Build's one Maven call runs with `-q`, so its log cannot show downloads after a hit; the
  cause is inferred from the key and the snapshot dependency.
