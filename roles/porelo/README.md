# porelo

Porelo on the host, everything through Porelo's own commands: Porelo installed from its repository by its pinned key and
its setup script run for the account (`tasks_from: install`), `porelo setup` and `porelo vault status` naming
`vault-new` with `keys`, or `vault`, in `porelo_host_needs` while the vault is missing or shut, the machine file's keys
checked in the vault and its project followed by its signature (`tasks_from: project`), and every agent offered by
Porelo's repository installed (`tasks_from: tasks`). The machine file holds only `project` and `keys`; the role reads
Porelo's inventory version 2 from `porelo project inventory --machine-file` (stopping with Porelo's words on `65` or
`66`), tells the vault's state from `porelo vault status` (`0` open, `3` shut, `4` missing), refuses naming each key of
the machine file that `porelo vault list` lacks, follows the project only where `porelo project following --json`
differs, and reads the offered agents and the open vault from the setup script's `--list --json` and `porelo agents
--json`. `up` starts no task and does not stop for an agent's sign-in: the person starts tasks and signs an agent in
when needed. Where the project names transports, the role installs their packages and, for `matrix`,
`porelo-matrix-homeserver` through Porelo's setup script, enabling nothing: the transport's `setup` enables and starts
the homeserver at the first task start.

Where `porelo_host_forge` is true, `install` also installs `porelo-adapter-forgejo` from Porelo's apt repository,
providing `/usr/libexec/porelo/builds/forgejo`. The forge role deposits the gate and reader's shared token into the
account's vault as `git.token.forge.porelo.internal` when repositories are configured.
`~/.config/porelo/ca-certificates.pem` holds the forge's CA in a marked block beside
the person's own certificates, and `~/.config/porelo/task-ca-certificates.pem` holds the forge's CA alone; both are
owned by the account with mode `0600`, in its `0700` Porelo configuration directory. `down` removes that block and the
task CA file, and removes the account's CA bundle if only whitespace remains.
Whatever the forge, `~/.config/containers/containers.conf.d/porelo-host-hosts.conf` keeps the host's `/etc/hosts` out
of the account's containers, since its loopback entry for the forge would hide the gate's address Porelo's resolver
gives a task, and the room's name would name the person's computer; `down` removes it.

The machine file and the project's bundle it names come from the interface, which uploads them over ssh into
`/etc/porelo-host/setup/` before `up`, each root's alone. Once Porelo's setup script has made the account, `install`
gives the directory and its files the account's group (`0750`, `0640`), so the account reads them and never writes
them, since `machine.yml` pins the project's signing key. `project` refuses before Porelo reads anything where the
directory or `machine.yml` is missing, is not root's, or can be written by its group or others, naming each with its
owner and mode; `down` removes the directory.

The person's stop, `porelo-host-stop` in `/usr/local/bin`, is installed by `install`, which also names the account in
`/etc/porelo-host/stop.conf`, root's with mode `0644` and no secret. Run by the person as the account, it asks in their
terminal; run as root with `--stdin`, it takes every need from the person's secrets file, one base64 line each, and
passes each value on a pipe into its user: the vault's passphrase into `porelo vault init` or `unlock`, each key into
`porelo vault put`, as the account, and the room's registration token (`matrix-token`) into the account's
`~/.config/porelo/matrix/host-registration-token`, written as the account. The keys reach the vault only so, never
through Ansible; the [line contract](../../doc/lines.md) has the form and the exits. Where the followed project names
that file as `registration_token_file` (Porelo's inventory names a transport's `*_file` settings), `project` refuses
another path with a message beginning `registration_token_file:`, and refuses with `matrix-token:` while the account
holds no such token of its own with mode `0600` in its own directories of mode `0700`.

At `down` (`tasks_from: down`), `porelo task stop --all` stops every running task of the account, keeping their
containers and workspaces, before the vault is cleared (`porelo vault clear --yes`, with `--force` on a shut vault), and
removes `stop.conf`, `/etc/porelo-host/setup/` and the account's room token, which `vault clear` does not reach. If a task survives, `down` fails with Porelo's words and leaves the vault in place.

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
| `porelo_machine_file` | `/etc/porelo-host/setup/machine.yml` | The person's machine file, uploaded by the interface into the setup directory, which Porelo reads. |

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
