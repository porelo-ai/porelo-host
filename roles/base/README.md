# base

The host's base: the packages every host gets, KVM with libvirt running, and podman, installed machine-wide, the SSH forwarding policy and the public-interface firewall; the
`controllers` check for an account's delegated cgroup controllers; and `tasks_from: host` at the end of `up`, writing
`/etc/porelo-host/host.json` (`0644`) and printing `porelo-host: host {json}` with what a project's `access.yml` needs
of the host.

## Requirements

Ubuntu 26.04, run as root on the host itself (`-c local`). A CPU with virtualization: the role stops on one without
`vmx` or `svm`, before it installs anything.

## Variables

| Variable | Default | What it is |
|---|---|---|
| `base_packages` | `[acl, ca-certificates, curl, git, nftables, openssh-server]` | Packages beside KVM's and podman's. |
| `base_account` | required when called | An existing account; for `tasks_from: account`, `controllers` or `down`. |
| `base_host_path` | `/etc/porelo-host/host.json` | Where `tasks_from: host` writes the host's public summary JSON. |

`base_host_admin_key_file` defaults to `/root/.ssh/authorized_keys`, which setup must populate with the pinned
host admin key. Every `up` copies it to `/etc/ssh/authorized_keys/root` before enabling the SSH policy. A handover
updates this source as well as the active root-owned key file. See [SSH access](../../doc/ssh.md).

## Example

    - name: Bring the host up
      hosts: localhost
      connection: local
      roles:
        - porelo.host.base

## Behaviour

**Idempotent**: a second run changes nothing, measured by Molecule's idempotence step. **Check mode**: the reading
tasks run in it too, so the checks hold; a check run is not tested yet. **Rollback** is not offered: the packages
stay; the host is given back whole. The `controllers` entry point checks that an existing `base_account`'s user manager
delegates `cpu`, `memory` and `pids`; the forge and Matrix roles call it after making their accounts, before starting
their containers.

## License

GPL-3.0-or-later.
