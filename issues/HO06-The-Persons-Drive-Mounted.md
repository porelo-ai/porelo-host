# HO06 — The Person's Drive Mounted

**Status:** Backlog.
**Size:** M - one role around a third-party client that runs headless, whose login only the person can give, and
whose `down` must wait until everything written is synced.

**What must be true.** At `up`, the person's drive is there on the host, read and written, its one folder only, and
nothing is run from it; at `down` it is unmounted, with everything written to it synced first.

## Plan

- **Tresorit's own client, headless**: Tresorit for Linux ships `tresorit-cli` and `tresorit-daemon`, made for
  servers without a desktop. It syncs a tresor two ways into a local folder (`tresorit-cli sync --start <tresor>
  --path <dir>`); it is not a mount, so "mounted" here means that folder, synced.
- **One role, `drive`**: `install.yml` (the installer for the account, under its home, its digest checked before it
  runs), `service.yml` (a systemd user unit for `tresorit-daemon`, with the linger Porelo's setup
  script gives the account),
  `sync.yml` (exactly one tresor, `drive_tresor`, into `drive_path`; any other sync the daemon reports is stopped,
  so only that one folder is on the host).
- **The login is the person's**: `tresorit-cli login` asks for the account's password, which never passes through
  Ansible. Decided: `up` stops for it once, where it stops for the vault ([HO02](README.md#ho02)), and names both
  commands; the
  second play checks the login and the sync (`tresorit-cli status`) and stops, naming the step, when either is
  missing.
- **Nothing run from it**: `drive_path` lies on a filesystem mounted `noexec,nosuid,nodev`, a file-backed one made by
  the role if the host has no such partition, so nothing synced in can be started.
- **At `down`**: wait until the daemon reports the tresor synced, with a limit, and stop with the reason if it does
  not; then `sync --stop`, `logout`, the daemon stopped and the folder's filesystem unmounted.
- **Decided: Tresorit is left out of the Molecule tests**. They test the role against a local folder in the tresor's
  place, with the client's steps switched off by one variable, `drive_client`; Tresorit itself is met only at a real
  `up`.
- **Red first**: `verify.yml` runs a script copied into `drive_path` and asserts it is refused; it fails without
  the `noexec` mount.

## Acceptance

- On the test VM `build/molecule.sh` makes, with a local folder in the tresor's place: the folder is there after `up`, on its
  `noexec` filesystem, and unmounted after `down`; `idempotence` reports `changed=0`.
- At the first real `up`: a file written on the host before `down` is in the tresor afterwards, and a file put into
  the tresor elsewhere is on the host after the next `up`; a sync that does not finish within its limit stops `down`,
  naming the tresor.
- No executable in `drive_path` runs; the Tresorit password appears in no output of the run.

## To be checked

- The installer's address, and whether Tresorit names a digest or a signature for it; if not, the installer is
  pinned by a digest taken once and written into the role.
- Whether the daemon runs as an unprivileged account on Ubuntu 26.04, and which `tresorit-cli status` output
  says "synced", read from the client itself.
- Whether `tresorit-cli login --email <address> --password-on-stdin` logs in over `ssh … bash -s` with no terminal,
  once without and once with a second factor on the account, so porelo-frontend can give the login as it gives the
  vault's passphrase; read in Tresorit's documentation, not yet measured.
- That the role adds `drive` to `porelo_host_needs` in `up`'s first play while the drive is logged out or not synced,
  so the second play stops with the waiting line `doc/lines.md` describes; [HO09](README.md#ho09) built that stop and leaves its
  acceptance here.
