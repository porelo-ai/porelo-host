# base

The host's base: the packages every host gets, KVM with libvirt running, and podman, installed machine-wide; and, as a
second entry point run after Porelo's setup script made the account, that account in KVM's and libvirt's groups.

## Requirements

Ubuntu 26.04, run as root on the host itself (`-c local`). A CPU with virtualization: the role stops on one without
`vmx` or `svm`, before it installs anything.

## Variables

| Variable | Default | What it is |
|---|---|---|
| `base_packages` | `[acl, ca-certificates, curl, git]` | Packages beside KVM's and podman's. |
| `base_account` | `{{ porelo_host_account }}` | An existing account; for `tasks_from: account` or `controllers`. |

## Example

    - name: Bring the host up
      hosts: localhost
      connection: local
      roles:
        - porelo.host.base
      tasks:
        - name: Let Porelo's account open KVM and libvirt
          ansible.builtin.include_role:
            name: porelo.host.base
            tasks_from: account

## Behaviour

**Idempotent**: a second run changes nothing, measured by Molecule's idempotence step. **Check mode**: the reading
tasks run in it too, so the checks hold; a check run is not tested yet. **Rollback** is not offered: the packages
and the group memberships stay; the host is given back whole. The account's linger and its subuid and subgid ranges
are made by Porelo's setup script, and this role only checks them, stopping when one is missing.
The account part also checks its user manager's delegated `cpu`, `memory` and `pids` controllers. The `controllers`
entry point makes the same read-only check for any existing `base_account`; the forge calls it after making its
two accounts, before starting their containers.

## License

GPL-3.0-or-later.
