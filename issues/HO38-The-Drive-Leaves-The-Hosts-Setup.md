# HO38 — The Drive Leaves The Host's Setup

**Status:** Implementing.
**Size:** M - mostly removal: a role, a module and its tests, the stop's `drive` and `--email`, and the drive's part of
the Molecule scenario, with the docs that describe them; no new contract, since porelo-frontend's
[F201](https://github.com/porelo-ai/porelo-frontend/blob/main/issues/README.md#f201) mounts a user's drive outside the
host's setup.

**What must be true.** A host comes up and goes down with nothing of Tresorit: no client installed, no login asked at
`up`'s stop, no folder mounted and no sync waited on at `down`. A user's own drive is that user's, mounted in their own
account by the interface's per-user setup on any machine with Porelo, and is no part of renting a host or of `up`.

## Plan

Read in the code, nothing measured. Once [HO36](README.md#ho36) reads `machine.yml` and the bundle from
`/etc/porelo-host/setup/`, nothing of the setup is on the drive, so the drive's step can go whole.

- **Out of the playbooks:** `playbooks/up.yml` loses its step `Give the person's drive its folder` (`porelo.host.drive`)
  and `playbooks/down.yml` the drive's part, so the stop never names `drive` and `down` waits on no sync.
- **Out of the collection:** the role `roles/drive/` goes whole, with the module `plugins/modules/tresorit_installer.py`,
  its unit tests `tests/unit/plugins/modules/` and their plays, and the collection variable `porelo_host_tresor`.
  Nothing else in the collection mounts a drive; a user's drive is the interface's.
- **The stop:** `roles/porelo/files/porelo-host-stop` loses `drive`, `--email` and the e-mail prompt; without
  `--stdin` it keeps `vault-new` and `vault` for a person at the host's terminal. Its unit tests
  (`tests/unit/roles/test_porelo_host_stop.py`) drop the drive's cases and gain one refusing `drive` with exit 64.
- **What names the drive goes with it:** the comments in `roles/base/defaults/main.yml` and
  `roles/base/tasks/account.yml` that the drive is logged in as Porelo's account, `porelo_machine_file`'s old default
  (gone with [HO36](README.md#ho36)), the drive's rows in `doc/index.md`, `doc/lines.md` (`drive` among the needs),
  `doc/testing.md` (the client's stub), `doc/local-forge.md` (the drive's sync wait at `down`), `doc/decisions.md`
  (*Tresorit's installer*, and *The order of `up` and `down`*, which names the drive's login),
  `roles/porelo/README.md` (the stop's drive login), and the Build's step *The plugins' Python and their tests* in
  `.github/workflows/build.yml`, which compiles `plugins/modules/tresorit_installer.py`. The open issues that name the
  drive follow in the same commit: [HO14](README.md#ho14) (the module) and [HO15](README.md#ho15) (the drive's mount,
  daemon and installer on Fedora).
- **The Molecule scenario** loses the client's stub (`files/tresorit-cli`), the drive's login, the first `up`'s
  `drive` need, the sync and unmount checks in `verify.yml`, `side_effect.yml`'s down that waits on an unsynced
  drive, and the drive's folder in `tasks/secrets_stdin.yml`, whose search for a secret moves to wherever
  [HO36](README.md#ho36) puts the setup's files; it gains a check that nothing of Tresorit is on the host after `up`.
- **Touches:** `playbooks/up.yml`, `playbooks/down.yml`, `roles/drive/` (removed), `plugins/modules/tresorit_installer.py`
  (removed), `tests/unit/plugins/modules/` (removed), `tests/unit/plugins/callback/plays/waiting.yml` and
  `test_lines.py` (their example needs), `tests/unit/roles/test_porelo_host_stop.py`,
  `tests/unit/roles/test_down_after_failed_up.py`, `roles/porelo/files/porelo-host-stop`, `roles/porelo/README.md`,
  `roles/base/defaults/main.yml`, `roles/base/tasks/account.yml`, `.github/workflows/build.yml`, `doc/index.md`,
  `doc/lines.md`, `doc/testing.md`, `doc/local-forge.md`, `doc/decisions.md`, `CHANGELOG.md`, the issues
  [HO14](README.md#ho14) and [HO15](README.md#ho15), and the Molecule scenario's `converge.yml`, `verify.yml`,
  `side_effect.yml`, `tasks/secrets_stdin.yml` and `files/tresorit-cli` (removed).
- **Red first:** the unit test of the stop refusing `drive`; in Molecule, the first `up`'s needs without `drive`, and
  after `up` no `tresorit-cli`, no Tresorit unit, and nothing mounted under `/srv/porelo-host/drive`.

## Acceptance

- A rented host comes up with only the master password and sudo typed, and nothing of Tresorit is installed or asked.
- `down` waits on no sync and unmounts nothing of a drive.
- `porelo-host-stop drive` is refused with exit 64.
