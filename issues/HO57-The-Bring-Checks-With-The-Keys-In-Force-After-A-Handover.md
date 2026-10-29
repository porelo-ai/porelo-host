# HO57 — The Bring Checks With The Keys In Force After A Handover

**Status:** Accepted. It waits for porelo's B332, which names the pinned keys themselves.
**Size:** S - one variable, two arguments and a scenario step, with a VM run; measured S median 54 min, one
measurement.

**What must be true.** A second bring verifies only what is new since the followed commit, `porelo project verify
--since <followed commit>`, given the keys in force there. Today it verifies from registration with the machine file's
key and no `--since`, walking every handover again, since `porelo project following --json` names the pinned keys
only by fingerprint, which verify refuses; with B332 it names them as `signed_by_keys`.

## Plan

- `__porelo_own_signers` in `roles/porelo/vars/main.yml` takes `signed_by_keys` of the followed entry, the machine
  file's key for a project not followed yet, and `roles/porelo/tasks/own.yml` passes `--since` and `--access-since`
  again.
- `roles/porelo/tasks/project.yml` compares the machine file's key with those keys, not with the fingerprints, so a
  second run follows nothing.
- The scenario's second bring after a handover, seen red first.
