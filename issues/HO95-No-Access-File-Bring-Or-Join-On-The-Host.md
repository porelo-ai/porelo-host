# HO95 — No Access File, Bring Or Join On The Host

**Status:** Implementing.
**Replaces:** [HO45](README.md#ho45): nothing is brought or joined in a person's own account any more; the migration goes on in [HO94](README.md#ho94).
**Size:** M - two playbooks, the roles' own-account tasks, the setup bundles, the access file's reading in the person
helper, `up`'s printed block, their tests and documents.

**What must be true.** Nothing on the host reads a project's access file, takes an uploaded bundle, or runs a bring
or a join; the host's `admins` name its host admins alone, and no developer is pinned there.

## Plan

- Go: `playbooks/bring.yml`, `playbooks/join.yml`, `roles/porelo/tasks/own.yml`, `own_sync.yml`, `project.yml`'s
  bundle handling, `roles/forge/tasks/own.yml` and `own_push.yml`'s bring parts, the setup directory in the data folder
  `porelo-host/setup/<project>/` in the data folder, the per-person sync timer, and the `host:` block `up` prints.
- `roles/porelo/files/porelo-host-person`: `sync <project>` stops reading the access file through Porelo's verify;
  persons and roles come from the state the host follows. A developer under the host's `admins` is no longer read.
- The push config each person's push reads is written by the host for each member, not by a bring.
- Tests that hold the removed paths go with them; a test shows that a leftover setup directory or access bundle is
  never read.

## Acceptance

- A search finds no access file, bundle, bring or join in the collection, its tests or its documents, apart from the
  changelog's entry naming their removal.
- The unit suite and Molecule pass without them.
