# HO57 — The Bring Checks With The Keys In Force After A Handover

**Status:** Idea; blocked by porelo's B332.

**What must be true.** A bring after a handover that changed the project's signers passes `porelo project verify
--since <followed commit>`, given the keys pinned since. Today the host passes the machine file's key, since
`porelo project following --json` names the pinned keys only by fingerprint, which verify refuses; with B332 it names
them as `signed_by_keys`.

## Plan

- `__porelo_own_signers` in `roles/porelo/vars/main.yml` takes `signed_by_keys` of the followed entry, the machine
  file's key for a project not followed yet.
- `roles/porelo/tasks/project.yml` compares the machine file's key with those keys, not with the fingerprints, so a
  second run follows nothing.
- The scenario's second bring after a handover, seen red first.
