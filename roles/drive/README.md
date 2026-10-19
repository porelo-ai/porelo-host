# drive

The person's drive on the host: one folder, read and written, on a filesystem of its own that is mounted `noexec`,
`nosuid` and `nodev`, so nothing synced into it can be started. The filesystem lives in a sparse file and is mounted
by a systemd mount unit, so it comes back at every boot. Tresorit's client is installed for the account from
Tresorit's own installer, which runs only once `porelo.host.tresorit_installer` found it signed under the pinned CA.
Its daemon runs as a user unit of the account, `tresorit-daemon.service`, kept running by the account's linger and
started again after a crash.

While the client is logged out, the role adds `drive` to `porelo_host_needs`, and `up`'s second play stops for the
person's login. Logged in, it syncs `drive_tresor` into the folder, stops every other sync the client has, and waits
until the tresor reads `idle` with nothing left. `down` waits the same way, then stops the sync, logs out with
`--unlink` so the host leaves no device on the person's account, stops the daemon and unmounts the folder. `tasks_from: down` takes it down, last at `down`.

## Requirements

Ubuntu 26.04, run as root on the host itself (`-c local`), after Porelo's setup script made the account.

## Variables

| Variable | Default | What it is |
|---|---|---|
| `drive_account` | `{{ porelo_host_account }}` | The account the folder belongs to. |
| `drive_path` | `/srv/porelo-host/drive` | Where the folder is. |
| `drive_image` | `/var/lib/porelo-host/drive.img` | The sparse file its filesystem lives in. |
| `drive_size` | `20G` | How large that file may grow. |
| `drive_client` | `true` | Whether Tresorit's client syncs the person's tresor into the folder. |
| `drive_tresor` | `{{ porelo_host_tresor }}` | The person's tresor synced into the folder, by name. |
| `drive_sync_wait` | `900` | How long `up` and `down` wait, in seconds, for the tresor to read synced. |
| `drive_installer_url` | Tresorit's own address | Tresorit's Linux installer, as Tresorit's site serves it. |
| `drive_installer_ca_sha256` | `AC:46:31:BC:…:3D:D2:42` | The fingerprint of the CA that issues the installer's signing certificate. |

## Example

    - name: Bring the host up
      hosts: localhost
      connection: local
      roles:
        - porelo.host.drive

## Behaviour

**Idempotent**: a second run changes nothing, measured by Molecule's idempotence step. **Check mode** is not tested.
**Rollback** is not offered; `down` unmounts the drive, and the file it lives in goes with the host.

## License

GPL-3.0-or-later.
