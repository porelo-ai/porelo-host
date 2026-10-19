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

- [x] On the test VM `build/molecule.sh` makes: the folder is there after `up`, on its `noexec` filesystem, and
  unmounted after `down`; `idempotence` reports `changed=0`; no executable in `drive_path` runs.
- [x] With the client's stub: a logged-out client stops the first `up` with rc 2 and one waiting line naming
  `drive` alone; after the login `up` runs through, the person's tresor syncs into `drive_path` and no other does;
  `down` logs the client out with `--unlink` and stops every sync. This is the stop's acceptance
  [HO09](README.md#ho09) left here.
- [ ] At the first real `up`: a file written on the host before `down` is in the tresor afterwards, and a file put
  into the tresor elsewhere is on the host after the next `up`; a sync that does not finish within its limit stops
  `down`, naming the tresor. Measured by hand on `ubuntu26.04` both ways (see Measured), not yet by `up` and `down`.
- [ ] The Tresorit password appears in no output of the run.

## Built

- `0a4a42e`: the folder's filesystem, its mount unit and `down`'s unmount, with Molecule's verify and side effect.
- `702b0e7`: the installer checked by `porelo.host.tresorit_installer` against the pinned CA (QH17, decided (a)
  after the operator's own download matched), then installed as the account.
- The daemon as the account's user unit `tresorit-daemon.service`, `Type=forking`.
- `sync.yml`, as measured: logged out, the role adds `drive` to `porelo_host_needs` and `up`'s second play stops
  with the waiting line; logged in, it syncs `drive_tresor` into `drive_path` with `sync --start … --path`, stops
  every other sync, and waits until `transfers` reads `idle 0 0` twice, within `drive_sync_wait`. `down` waits the
  same way, then `sync --stop`, `logout --unlink`, the daemon stopped and the folder unmounted. An installed client
  is left to update itself; ext4's `lost+found` is removed from the folder.
- In Molecule a stub of `tresorit-cli` (`extensions/molecule/default/files/`) answers as the client was measured, so
  the role's steps around the client run in the Build; Tresorit itself is met only at a real `up`. Seen red first:
  without the `drive` need the first `up` ran through with rc 0.
- The fourth full Scaleway run (2026-10-19) stopped at the drive's login: porelo-host logs in over ssh as the account,
  which held no key of the person's. `base`'s account step now lets `porelo_host_authorized_key` in as the account,
  and `down` takes it off last; Molecule logs in with it as the account and is refused after `down`, seen red first
  with the run's very refusal.

## Measured

On Ubuntu 26.04 in a VM of `build/molecule.sh`'s, with `drive_client` on, client 3.5.1300.4870, logged out:
- `up` installs and starts the client with no failed line, and a second `up` changes nothing.
- The daemon runs as the account. Started directly, it forks into a session of its own at once, so the unit is
  `Type=forking`. systemd finds its main PID, and `kill -9` of it restarts the unit within its `RestartSec`.
- `tresorit-cli -p status` is tab-separated, `Logged in as:\t-` while logged out, rc 0. `tresors` and `transfers`
  answer rc 1 `CLINotLoggedIn`.
- `login` takes `--email <address> --password-on-stdin`. A second factor is either `--totp <code>` or, without it,
  a prompt (help text, not yet measured).
- `drive --mount <path>` is Tresorit Drive, all tresors in one mount, which the role does not use.

Logged in, once, on `ubuntu26.04` as the account `machines`, with the operator's own login and a tresor made for the
test (QH18), 2026-10-19:
- Logged in, `sync --start <tresor> --path <dir>` is there (logged out, its help names no `--path`); rc 0, and
  `tresors -p` then names the path in its second column, `-` while not synced.
- `transfers -p --tresor <tresor>` gives `<tresor>\t<state>\t<files left>\t<errors>`. The states seen: `indexing`
  after a write, `syncing 1 0` while uploading, `idle 0 0` once synced; a 2 MB file and a small one were up within
  about 8 s. A tresor not synced answers rc 1 `CLITresorNotSynced`.
- Files written on the host reached the operator's client, and a file put into the tresor there reached the host
  within seconds. Synced files are `0664` with an ACL; the client keeps a `.tresorit` directory in the path.
- `sync --stop` leaves the files in place; `logout --unlink` answers rc 0 and logs the device out.
- The second factor needs no argument: with the password and then the one-time code piped as two lines over
  `ssh -T`, no terminal on the host, the client printed "Enter your one time password", read the code from that same
  stdin and logged in (the operator typed nothing at its prompt).
- Through `sudo -u <account>` from another account's session the client answered `CLIDaemonNotRunning`; as the
  account itself, over ssh, it reaches the daemon. `host up` logs in as the account.

## To be checked

- The first real `up` and `down` with the person's own drive, as the acceptance's third item says.
