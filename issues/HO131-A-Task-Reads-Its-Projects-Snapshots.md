# HO131 — A Task Reads Its Project's Snapshots

```json
{
  "$schema": "issue-1.json",
  "id": "HO131",
  "title": "A Task Reads Its Project's Snapshots",
  "state": "Review",
  "size": "S",
  "priority": "Medium",
  "rank": 22,
  "blockedBy": [],
  "covers": "A task's token also reads its organization's packages, `read:package`, so a task resolves its project's snapshots from the host's forge; it writes none."
}
```

**Why this size.** one scope in `porelo-host-person`'s task token, its unit test, a Molecule step on the real forge and the
documents.

**What must be true.** A task on the host resolves its project's snapshots from the host's forge with the token the
host made for it at its start. That token reads the packages of the task's organization and writes none. Porelo's task
gate, not the token, bounds it to the task's own project.

## Plan

- `roles/porelo/files/porelo-host-person`: `TASK_SCOPES` becomes `write:repository,read:package`. The account
  `porelo-<login>` already reads the organization's packages through its `developers` team (`repo.packages: read`);
  Forgejo 17.0.0 answers a `write:repository` token there `401`, measured in Molecule with a real task start. The task
  start still answers one token alone on stdout. A write stays refused twice: by the scope, and by the team, which
  reads packages only; Molecule saw a `write:package` task token refused too.
- Red first in `tests/unit/roles/test_porelo_host_person_tasks.py`: the task token is asked with exactly
  `write:repository,read:package`.
- Molecule, on the real Forgejo, with a token from a real task start: it reads a package of its organization (200), its
  `PUT` of a name nobody holds is refused (401 or 403), and a package of an organization its person is not in is
  refused; a generic package, as Forgejo checks the scope alike for every kind. All it makes goes, also after a failure.
- `doc/task-certificates.md` and `doc/local-forge.md` name the scope; `CHANGELOG.md`.

## Acceptance

- The unit test seen failing without the change; Molecule's step green on the local VM, each refusal seen red first.

## To be checked

- A real task's Maven resolving a snapshot through its gate needs a host with Porelo's task start and the forge
  together; it is not measured here.
