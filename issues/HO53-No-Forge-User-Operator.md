# HO53 — No Forge User Operator

**Status:** Review.
**Size:** S - the forge role's person step, the password helper's direct-root path, their tests and a Molecule act.

**What must be true.** `up` makes no forge user `operator`, and a host set up before has none left. Each person's forge
login is the one [HO43](README.md#ho43) admits under their own name, so a project admin named `operator` is admitted
like anyone else; on Ubuntu no person can be named `operator`, which a system group holds.

## Plan

- **The decision** (operator's, relayed by the Coordinator in the room, 2026-10-29): `up` stops making the forge user
  `operator`, on hosts already set up too.
- **First shown, then removed:** a search of the collection, its tests and Molecule for every reader of
  `forge_person`, of `person=` in `/etc/porelo-host/forge.conf` and of the login `operator`, each named in this issue
  with what it reads, before anything is taken away.
- **Removed:** `forge_person` and its step, `person=` in `forge.conf`, the direct-root path of
  `porelo-host-forge-password` (a sudo call keeps setting the caller's own login); on a host set up before, `up`
  deletes a forge user `operator` that is no person in `/etc/porelo-host/people/`, and drops `person=`.
- **Tests first:** no task names `forge_person`; the password helper refuses a direct root call without `SUDO_USER`;
  each red before the change.

### Readers found

- `roles/forge/defaults/main.yml`: sets default `forge_person: operator`.
- `roles/forge/meta/argument_specs.yml`: declares `forge_person` (default `operator`) in the `main` and `request`
  argument specs.
- `roles/forge/tasks/request.yml`: reads `forge_person` to write `person={{ forge_person }}` into
  `/etc/porelo-host/forge.conf`.
- `roles/forge/tasks/main.yml` and `roles/forge/tasks/person.yml`: `main.yml` includes `tasks/person.yml`, which reads
  `forge_person` to validate the login name, check `forgejo admin user list`, and create the Forgejo user
  `{{ forge_person }}` (alongside installing `/usr/local/sbin/porelo-host-forge-password` and
  `/usr/local/sbin/porelo-host-project`).
- `roles/forge/tasks/owner.yml`: reads `forge_person` to add `{{ forge_person }}` to `{{ forge_owner }}`'s `Owners`
  team (task file uncalled by `up`).
- `roles/forge/tasks/protection.yml`: reads `forge_person` for `approvals_whitelist_username`,
  `merge_whitelist_usernames` and the assertion failure message on `main`'s branch protection rule (task file uncalled
  by `up`).
- `roles/forge/files/porelo-host-forge-password`: reads `person=` from `/etc/porelo-host/forge.conf` in
  `configuration()` when called directly as root without a non-root `SUDO_USER`/`SUDO_UID`. (`porelo-host-person`,
  `porelo-host-project` and `porelo-host-stop` read `forge.conf` without using `person=`.)
- `roles/forge/README.md` and `doc/local-forge.md`: read/describe `person` in `/etc/porelo-host/forge.conf` and
  `forge_person` (default `operator`) as the person's forge login and `main` approver/merger.
- `tests/unit/roles/test_porelo_host_forge_password.py` and `tests/unit/roles/test_porelo_host_project.py`: write
  `person=bob` (read by the direct-root password test and ignored by the `sudo` test) and `person=alice` (unread by
  `porelo-host-project`) in `forge.conf` fixtures.
- `extensions/molecule/default/verify.yml` and `extensions/molecule/default/tasks/forge_person.yml`: `verify.yml`
  includes `tasks/forge_person.yml`, deletes Forgejo user `operator` before `up -vvv`, and includes
  `tasks/forge_person.yml` again after `up -vvv`; `tasks/forge_person.yml` asserts `'operator'` is in Forgejo's user
  list, calls `porelo-host-forge-password` directly as root without `SUDO_USER`, and signs in at `/user/login` as
  `user_name=operator`.

## Acceptance

- Molecule: after `up`, the forge lists no user `operator`; a host prepared by the version before, then brought up
  again, has none left; admitting a person named `operator` is refused (65) and makes nothing, since Ubuntu's
  `base-passwd` holds a system group `operator` (GID 37) that `useradd --user-group` would collide with (measured by
  agy; `porelo-host-person` now refuses any new person whose name a group already holds).
