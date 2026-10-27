# HO38 — The Drive Leaves The Host's Setup

**Status:** Backlog; blocked by [HO36](README.md#ho36).
**Size:** L - `up` and `down` run the drive's step only where the person chose a drive, the role changes whose account
it serves, the drive's login moves to the person's account, and that account is a contract with porelo-frontend, whose
[F201](https://github.com/porelo-ai/porelo-frontend/blob/main/issues/README.md#f201) mounts the drive from it.

**What must be true.** A host comes up with no drive at all: no Tresorit login at `up`, no sync wait at `down`. A person
who wants their own files on the host chooses a personal drive, which is mounted in their own account and never in
Porelo's, so nothing Porelo's tasks run can read it.

## Plan

Read in the code, nothing measured.

- **Out of the host's setup:** `playbooks/up.yml`'s first play keeps its `porelo.host.drive` step, after the
  account's part of `base`, but runs it only `when: porelo_host_drive is defined`, and `playbooks/down.yml` takes the
  drive down under the same condition. The need `drive` then comes only from that step, so the stop names it only for
  a person who chose a drive.
- **The role serves the person's account:** a new collection variable `porelo_host_drive`, absent by default, which
  porelo-frontend's inventory writes with the tresor (`porelo_host_drive.tresor`) and the person's account
  (`porelo_host_drive.account`); `drive_account` and `drive_tresor` map them, `porelo_host_tresor` goes. The role's
  first task refuses an account `getent` does not know and one that is `porelo_host_account`, naming both.
  `drive_path` becomes `/srv/porelo-host/drive/<account>`, `0700` the account's, and `drive_image` one file per account.
- **Whose daemon:** Tresorit's daemon becomes a user unit of the person's account, which needs its linger, and the
  comments in `roles/base/defaults/main.yml` and `roles/base/tasks/account.yml` that porelo-host logs the drive in as
  Porelo's account go.
- **The stop's terminal for the drive** is a call of its own, run by the person logged in as their own account:
  `porelo-host-stop` runs as whoever calls it and switches no user, and since the drive's account is never Porelo's,
  one terminal call can no longer name `drive` with `vault-new` or `vault`. The script refuses such a call with exit
  64, naming both accounts, and `doc/lines.md` says which account each need is given in.
- **What stays as built:** the filesystem in a sparse file mounted `noexec`, `nosuid`, `nodev`, the checked installer,
  the sync wait and the logout with `--unlink` at `down`.
- **Touches:** `playbooks/up.yml`, `playbooks/down.yml`, `roles/drive/defaults/main.yml`, `meta/argument_specs.yml`,
  `README.md`, `tasks/main.yml` (the account's check), `filesystem.yml`, `service.yml`, `down.yml`, `down-client.yml`
  (its account is the person's), `roles/base/defaults/main.yml`, `roles/base/tasks/account.yml`,
  `roles/porelo/files/porelo-host-stop`, `doc/index.md`, `doc/lines.md`, and the Molecule scenario, which runs once
  without a drive and once with a local one for a person's test account.
- **Red first, in Molecule:** an `up` without `porelo_host_drive` mounts nothing under `/srv/porelo-host/drive` and
  names no `drive`; one with it mounts the folder as the person's test account, and Porelo's account cannot list it;
  `porelo_host_drive.account` set to Porelo's account is refused before anything is mounted.

## Acceptance

- A rented host comes up with only the master password and sudo typed, and no Tresorit client is installed.
- A host rented again with a personal drive mounts it in the person's account; Porelo's account reads none of it.
- `down` on a host without a drive waits on no sync.

## To be checked

- With porelo-frontend: which account on the host is the person's - the admin the interface logs in as, or one of its
  own - who makes it, and that it has a linger for Tresorit's daemon.
- Whether the person's account needs the drive while it is not logged in, which decides between the linger and a
  daemon started only at its login.
