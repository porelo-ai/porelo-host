# porelo

Porelo on the host, everything through Porelo's own commands: Porelo installed from its repository by its pinned key and
its setup script run for the account (`tasks_from: install`), `porelo setup` and `porelo vault status` naming
`vault-new` or `vault` in `porelo_host_needs` while the vault is missing or shut, the machine file's keys deposited from
the drive into the vault and its project followed by its signature (`tasks_from: project`), and the packages the tasks
need installed, a stop with `agent-login:<agent>` for each agent whose sign-in the vault lacks, and the tasks started
(`tasks_from: tasks`). Where the project names transports, the role installs their packages and, for `matrix`,
`porelo-matrix-homeserver` through Porelo's setup script, enabling nothing: the transport's `setup` enables and starts
the homeserver at the first task start.

At `down` (`tasks_from: down`), the machine file's running tasks are stopped, keeping their containers and workspaces,
and the vault is cleared (`porelo vault clear --yes`).

## Requirements

Ubuntu 26.04, run as root on the host itself (`-c local`).

## Variables

| Variable | Default | What it is |
|---|---|---|
| `porelo_account` | `{{ porelo_host_account }}` | The account Porelo's setup script makes and Porelo's tasks run as. |
| `porelo_distribution` | `{{ porelo_host_distribution \| default('releases') }}` | Which of Porelo's published distributions (`releases` or `snapshots`) the host installs from. |
| `porelo_key_url` | in `defaults/main.yml` | Where Porelo's package key is fetched from. |
| `porelo_key_fingerprint` | in `defaults/main.yml` | The fingerprint the package key must have. |
| `porelo_repository_url` | in `defaults/main.yml` | Porelo's apt repository. |
| `porelo_setup_script` | `/usr/share/porelo/setup/porelo-setup.sh` | Porelo's setup script, as the package `porelo` ships it. |
| `porelo_machine_file` | `/srv/porelo-host/drive/porelo-host/machine.yml` | The person's machine file on their drive, which Porelo reads. |

## Example

    - name: Install Porelo and run its setup script for the account
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
