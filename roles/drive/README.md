# drive

The person's drive on the host: one folder, read and written, on a filesystem of its own that is mounted `noexec`,
`nosuid` and `nodev`, so nothing synced into it can be started. The filesystem lives in a sparse file and is mounted
by a systemd mount unit, so it comes back at every boot. `tasks_from: down` unmounts it, last at `down`.

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
