# porelo

Porelo's packages and person records on the host: `tasks_from: install` adds Porelo's apt repository by its pinned key,
installs `porelo` (and `porelo-adapter-forgejo`, providing `/usr/libexec/porelo/builds/forgejo`, when
`porelo_host_forge` is true), makes `/etc/porelo-host`, and installs `/usr/local/bin/porelo-host-stop`, running no
setup script for an account. `tasks_from: person` installs `/usr/local/sbin/porelo-host-person` (`add`, `lock`,
`purge` and `sync <project>`), private return-socket directories and the `porelo-people` sudoers rules for
`porelo-host-person sync *` (checked by the helper to the project's
unlocked recorded admin); `/etc/porelo-host/people/<user>.conf` records each person's `member=hand` and
`member=<project> project-admin|developer` memberships, `locked=` state and `laptop=` entries. `tasks_from: people`
runs at the start of `down` and refuses before anything is stopped while any record in `/etc/porelo-host/people/`
holds a membership, naming each person and their memberships with `"Take the project off"` and `"Purge"`.

Matrix admission stores no machine or registration token. Sync atomically publishes the verified access file's
`admins` list into `/etc/porelo-host/matrix/<project>.admins`, root:porelo-matrix `0640` in a `0750` directory;
project removal deletes it. Lock and purge run `porelo-message-transport-matrix expel <login>` as `porelo-matrix`,
including purge after a prior lock. See [Matrix access](../../doc/matrix.md) for the gate boundary.

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

SSH policy and initial key/KRL installation belong to `base`. The person helper creates
`/run/porelo-host/people/<login>` (0700, owned by the person) and a per-person tmpfiles rule at admission;
lock and purge remove both. Lock terminates sessions and stops the user manager even if a service hook refuses.
The verified registry reader supplies key/expiry and host-wide revocation inputs through the callable methods
in [SSH access](../../doc/ssh.md). Legacy laptop records remain readable without configuring VPN peers.
