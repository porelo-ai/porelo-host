# HO53 — No Forge User Operator

**Status:** Implementing; blocked by [HO42](README.md#ho42).
**Size:** S - the forge role's person step, the password helper's direct-root path, their tests and a Molecule act.

**What must be true.** `up` makes no forge user `operator`, and a host set up before has none left. Each person's forge
login is the one [HO43](README.md#ho43) admits under their own name, so a project admin named `operator` is admitted
like anyone else.

## Plan

- **The decision** (operator's, relayed by the Coordinator in the room, 2026-10-29): `up` stops making the forge user
  `operator`, on hosts already set up too.
- **First shown, then removed:** a search of the collection, its tests and Molecule for every reader of
  `forge_person`, of `person=` in `/etc/porelo-host/forge.conf` and of the login `operator`, each named in this issue
  with what it reads, before anything is taken away. Today's readers, by the code: the forge role's person step that
  makes the login and writes `person=`; the role's protection and owner steps; `porelo-host-forge-password` called
  directly by root, which sets that login's password; the argument specs and the role's README; Molecule's verify.
- **Removed:** `forge_person` and its step, `person=` in `forge.conf`, the direct-root path of
  `porelo-host-forge-password` (a sudo call keeps setting the caller's own login); on a host set up before, `up`
  deletes a forge user `operator` that is no person in `/etc/porelo-host/people/`, and drops `person=`.
- **Tests first:** no task names `forge_person`; the password helper refuses a direct root call without `SUDO_USER`;
  each red before the change.

## Acceptance

- Molecule: after `up`, the forge lists no user `operator`; a host prepared by the version before, then brought up
  again, has none left; a person admitted as `operator` gets their own login and tokens.
