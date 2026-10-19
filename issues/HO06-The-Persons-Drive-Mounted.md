# HO06 — The Person's Drive Mounted

**Status:** Implementing.
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

## Built

- `0a4a42e`: the folder's filesystem, its mount unit and `down`'s unmount, with Molecule's verify and side effect.
- `702b0e7`: the installer checked by `porelo.host.tresorit_installer` against the pinned CA (QH17, decided (a)
  after the operator's own download matched), then installed as the account.
- The daemon as the account's user unit `tresorit-daemon.service`, `Type=forking`.

## Measured

On Ubuntu 26.04 in a VM of `build/molecule.sh`'s, with `drive_client` on, client 3.5.1300.4870, logged out:
- `up` installs and starts the client with no failed line, and a second `up` changes nothing.
- The daemon runs as the account. Started directly, it forks into a session of its own at once, so the unit is
  `Type=forking`. systemd finds its main PID, and `kill -9` of it restarts the unit within its `RestartSec`.
- `tresorit-cli -p status` is tab-separated, `Logged in as:\t-` while logged out, rc 0. `tresors` and `transfers`
  answer rc 1 `CLINotLoggedIn`.
- `login` takes `--email <address> --password-on-stdin`. A second factor is either `--totp <code>` or, without it,
  a prompt (help text, not yet measured).
- **`sync --start <tresor>` takes no path**, unlike this plan's first reading. Where a tresor syncs to shows only in
  `tresors` once logged in. `drive --mount <path>` is Tresorit Drive, all tresors in one mount.

## To be checked

- With a login (QH18): where `sync --start` puts a tresor and whether that can be `drive_path`; what `transfers`
  says while syncing and once synced; whether the second factor's prompt reads stdin with no terminal.
- That the role adds `drive` to `porelo_host_needs` in `up`'s first play while the drive is logged out or not synced,
  so the second play stops with the waiting line `doc/lines.md` describes; [HO09](README.md#ho09) built that stop and leaves its
  acceptance here.
