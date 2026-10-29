# HO15 — The Host On Fedora

**Status:** Idea.

**What must be true.** `host up` brings a Fedora host up as it brings an Ubuntu 26.04 one, and `host down` takes it
down, with every role's promise kept the same way and proven by a Molecule scenario on Fedora; today every role is
Ubuntu 26.04 only.

## What differs and must be measured, nothing decided

- **SELinux in place of AppArmor**: whether `wg` may read the host's key in `/etc/wireguard` as it does on Ubuntu,
  and whether anything else of the roles needs a file context or a policy module.
- **firewalld, active by default**, beside the collection's own nftables table `inet porelo_host`: whether both hold
  together, or one must give way.
- **`dnf` and Fedora's own `ansible-core`**: the packages' names (`wireguard-tools`, KVM's, podman's), and the
  collection installed and run by Fedora's `ansible-core` from its tarball, as Ubuntu's is today.
- **A Molecule scenario on Fedora**, made by `build/molecule.sh` from a Fedora cloud image pinned by digest as
  `build/test-image` pins Ubuntu's.
- **porelo-frontend's part**, its own issue there: `host up` installs `ansible-core` with `dnf` on Fedora, chosen by the
  host's `/etc/os-release`, and a rented host is Fedora only where the provider offers it.

## What stays as it is

The systemd units (the firewall's, the VPN's, the forge's), and the stop's lines on standard input.
