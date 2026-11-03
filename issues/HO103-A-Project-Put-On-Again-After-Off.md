# HO103 — A Project Put On Again After Off

**Status:** Review.
**Size:** M - the helper's migration and removal, the follow's journal, the document and a check on a real forge.

**What must be true.** A project put on a host, taken off and put on again is taken. Today taking it off leaves the
host's deploy key at the central forge, and the new key has the same title, so Forgejo answers 422 and the helper
refuses, seen as `the central forge refused the deploy-key request (HTTP 422)`. GitHub's answer to the same title is not
measured. So `off` must also say truthfully what stays: nothing on the host, a deploy key at the central forge.

## Plan

- Read in the code: the removal runs in a follow, which holds no central token, so it cannot delete the key. The migration
  holds one and replaces it. Measured on the pinned Forgejo: a second key under one title answers 422, the same token
  deletes with 204 and then adds with 201, a read-only token's delete answers 403, and a title of 124 characters is taken.
- A project stands on one host at a time but can move, and the host it left may still hold it for unpushed work, using its
  key to compare. So `migrate` in `porelo-host-project` titles the key `porelo host <host> project <project>` and replaces
  only a read-only key of exactly that title with another public key; a writable one is refused and kept.
- `remove` answers each deploy key it leaves behind, by address and title, and the follow writes that to its journal.
- `doc/local-forge.md` says what stays, for a project and for the organization.
- A record that outlives a removal, as a refused room leaves it, is cleared when the project's forge organization is
  made anew, so the project is migrated again.
- GitHub's answer to a repeated title is not measured; deleting before adding does not depend on it.
- Red first in `test_porelo_host_project.py`: the round on a request-level forge that answers 422 as measured; and it is
  run once on the pinned Forgejo.

**The same for the organization.** A host's read key on the organization's repository is taken off by nobody: a host
set up anew or given up leaves its old key able to read until the repository's owner removes it. Its title comes from
Porelo and names the key's fingerprint, so a new host's key never collides; the document says what stays and who removes it.

## Acceptance

- On, off and on again succeeds against the pinned Forgejo and leaves one key; another host's key under its own title is
  untouched, seen failing with the title check broken on purpose.
- The journal and the document name the key `off` leaves at the central forge.
