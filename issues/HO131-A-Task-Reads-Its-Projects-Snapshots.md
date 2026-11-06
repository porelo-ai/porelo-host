# HO131 — A Task Reads Its Project's Snapshots

**Status:** Implementing.
**Size:** S - one scope in `porelo-host-person`'s task token, its unit test, a Molecule step on the real forge and the
documents.

**What must be true.** A task on the host resolves its project's snapshots from the host's forge with the token the
host made for it at its start. That token reads the packages of the task's organization and writes none. Porelo's task
gate, not the token, bounds it to the task's own project.

## Plan

- `roles/porelo/files/porelo-host-person`: `TASK_SCOPES` becomes `write:repository,read:package`. The account
  `porelo-<login>` already reads the organization's packages through its `developers` team (`repo.packages: read`);
  the token's scope is what Forgejo still refuses. The task start still answers one token alone on stdout.
- Red first in `tests/unit/roles/test_porelo_host_person_tasks.py`: the task token is asked with exactly
  `write:repository,read:package`.
- Molecule, on the real Forgejo: a task token reads a Maven file of its organization (200), its `PUT` there is refused,
  and a package of an organization its person is not in is not read.
- `doc/task-certificates.md` and `doc/local-forge.md` name the scope; `CHANGELOG.md`.

## Acceptance

- The unit test seen failing without the change; Molecule's step green on the local VM, each refusal seen red first.

## To be checked

- That Forgejo 17.0.0 refuses a `write:repository` token on `/api/packages` while the team grants the read: read in the
  scope model, not yet measured. Molecule's step measures it red first.
- A real task's Maven resolving a snapshot through its gate needs a host with Porelo's task start and the forge
  together; it is not measured here.
