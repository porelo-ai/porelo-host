# HO36 — The Host Reads The Files Its Setup Uploaded

**Status:** Review.
**Size:** M - a few lines in one role and its `down`, but a contract porelo-frontend writes (the place, its owner and
mode, and the paths in `machine.yml`), its docs and a Molecule check.

**What must be true.** The host's setup reads nothing from the drive: the interface uploads `machine.yml` and the
project's bundle over the ssh it already has into one place on the host that only root can write, and the host reads
them there, so no file of the setup lies on the drive.

## Plan

Read in the code, nothing measured. Agreed with porelo-frontend, whose
[F197](https://github.com/porelo-ai/porelo-frontend/blob/main/issues/README.md#f197) writes the files.

- **The place and its form:** `/etc/porelo-host/setup/`, written by the interface's `copy` step, which runs before
  the first play and so before Porelo's setup script makes the account: the directory `0700 root:root` with `sudo
  install -d`, each file `0600 root:root` with `sudo install -m 0600 -o root -g root /dev/stdin <file>`, each followed
  by its SHA-256 check on the host. Once the script has made the account, a task in `roles/porelo/tasks/install.yml`
  gives the directory and its files the account's group, `0750` and `0640`. The account reads them, since `porelo
  project inventory --machine-file` and `porelo project follow` run as the account, but never writes them, since
  `machine.yml` pins the project's signing key.
- **What lies there:** `machine.yml`, and `<project>.bundle`, the git bundle of the project's verified commit that
  `machine.yml`'s `project.url` names by its path there; `porelo project follow` clones it like any URL, and
  `signed_by` checks its commit. No secret lies there: [HO37](README.md#ho37) gives the vault's keys on standard input,
  so `machine.yml`'s `keys` name entries the vault already holds, and Porelo's refusal of a key path outside the
  machine file's directory touches no file.
- **The role reads it there:** `porelo_machine_file` in `roles/porelo/defaults/main.yml` becomes
  `/etc/porelo-host/setup/machine.yml`, from `/srv/porelo-host/drive/porelo-host/machine.yml`, with its entry in
  `roles/porelo/meta/argument_specs.yml` and `roles/porelo/README.md`.
- **The place checked before Porelo reads it:** a new first task of `roles/porelo/tasks/project.yml` refuses, naming
  the path and what it found, where the directory or `machine.yml` is missing, is not root's, or can be written by its
  group or others. A file on the old drive path is never read and never migrated.
- **`down` removes it:** `roles/porelo/tasks/down.yml` removes `/etc/porelo-host/setup/` after the vault is taken off,
  so nothing of the project is left on a host given back.
- **The drive stays mounted** and holds nothing the setup reads; [HO38](README.md#ho38) takes it out of the setup.
- **Touches:** `roles/porelo/defaults/main.yml`, `meta/argument_specs.yml`, `README.md`, `tasks/install.yml` (the
  group), `tasks/project.yml`, `tasks/down.yml`, `doc/index.md`, and the Molecule scenario's `converge.yml`, which
  writes `machine.yml` and the project into the place as `root:root` before `up`, as the interface does, in place of
  the drive.
- **Red first, in Molecule:** with `machine.yml` writable by the account, `up` stops naming the path before Porelo
  reads it; with the files in the place, `up` follows the project from the bundle; after `down`, the place is gone.

## Acceptance

- A rented host's `up` comes up with the uploaded files, and the drive's folder holds no `machine.yml` or bundle.
- A `machine.yml` the account can write, or one not root's, is refused with its path before Porelo reads it.
- After `down`, `/etc/porelo-host/setup/` is gone.
