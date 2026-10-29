# porelo

Porelo's packages on the host: `tasks_from: install` adds Porelo's apt repository by its pinned key, installs `porelo`
(and `porelo-adapter-forgejo`, providing `/usr/libexec/porelo/builds/forgejo`, when `porelo_host_forge` is true), makes
`/etc/porelo-host`, and installs `/usr/local/bin/porelo-host-stop`, running no setup script for an account.

The account-bound entry points (`main`, `project`, `tasks`, `down`) remain on disk for an explicit `porelo_account`
when called directly; `up` and `down` do not call them.

## Requirements

Ubuntu 26.04, run as root on the host itself (`-c local`).

## Variables

| Variable | Default | What it is |
|---|---|---|
| `porelo_distribution` | `{{ porelo_host_distribution \| default('releases') }}` | Which of Porelo's published distributions (`releases` or `snapshots`) the host installs from. |
| `porelo_key_url` | in `defaults/main.yml` | Where Porelo's package key is fetched from. |
| `porelo_key_fingerprint` | in `defaults/main.yml` | The fingerprint the package key must have. |
| `porelo_repository_url` | in `defaults/main.yml` | Porelo's apt repository. |
| `porelo_account` | required (account entry points only) | The account Porelo's tasks run as when an account entry point is called directly. |
| `porelo_setup_script` | `/usr/share/porelo/setup/porelo-setup.sh` | Porelo's setup script, as the package `porelo` ships it. |
| `porelo_machine_file` | `/etc/porelo-host/setup/machine.yml` | The machine file read by `project` and `down` when called directly. |

## Example

    - name: Install Porelo's packages and stop command
      hosts: localhost
      connection: local
      tasks:
        - name: Install Porelo
          ansible.builtin.include_role:
            name: porelo.host.porelo
            tasks_from: install

## Behaviour

**Idempotent**: a second run changes nothing, measured by Molecule's idempotence step. **Check mode**: the reading tasks
run in it too; a check run is not tested yet. **Rollback** is not offered; `down` stops the tasks and clears the vault,
and the packages stay with the host.

## License

GPL-3.0-or-later.
