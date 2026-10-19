# HO05 — The VPN

**Status:** Implementing.
**Size:** M - one role with a firewall and a key that must reach the host without passing through Ansible.

**What must be true.** The person reaches the host only through their own VPN, with the key from their drive, and
everything else the host offers listens only there; a second run changes nothing, and `down` leaves no peer that the
next start would collide with.

## Plan

- **Decided**: WireGuard, as a small role of this collection; it comes after the drive ([HO09](README.md#ho09)),
  whose file holds the host's key, and until it is up the host is reached over its public ssh only.
- **One role, `vpn`**, WireGuard (in the kernel since Linux 5.6, one key pair per peer): `install.yml` (the
  `wireguard-tools` package), `configure.yml` (the interface's file from a template with `{{ ansible_managed |
  comment }}`, mode `0600`, `backup: true`, notifying `vpn_restart`), `service.yml` (`wg-quick@<interface>` enabled
  and started), `firewall.yml` (nftables: on the public address only ssh and the VPN's UDP port; everything else only
  on the VPN's interface).
- **The host's private key never passes through Ansible**: the template holds `PostUp = wg set %i private-key
  <path>`, where `<path>` is the key's file on the person's drive ([HO06](README.md#ho06)), readable by root alone;
  the role checks the file is there and its mode, never reads it. The person's peer (its public key and address) comes
  from the inventory Porelo writes; a public key is not a secret.
- **Variables** `vpn_interface`, `vpn_port`, `vpn_address`, `vpn_peers`, `vpn_private_key_path`, in
  `meta/argument_specs.yml`; nothing from a provider's name.
- **At `down`**: the interface is stopped and its file removed, so the next `up` writes it again; the peer is the
  person's own and stays theirs.
- **Red first**: the scenario's `verify.yml` asserts that a port of a service bound to all addresses is not
  reachable on the public address; it fails without `firewall.yml`, then passes.

## Built

- The role as planned, in `up`'s second play after the person's step, since the key is on the drive and the drive is
  synced only after the person's login; `down` takes it down before the drive.
- **Ubuntu 26.04's AppArmor profile for `wg`** (from the `apparmor` package) lets it read only `/etc/wireguard`, and
  holds no `dac_read_search`, so `PostUp = wg set %i private-key <path>` failed with `fopen: Permission denied` for a
  key elsewhere. The role writes `/etc/apparmor.d/local/wg`, which the profile includes, with read for that one path
  and `dac_read_search`, since the drive's file is the account's; a copy into `/etc/wireguard` would be a second file
  holding the key.
- **The firewall** is a table of its own, `inet porelo_host`, loaded by `porelo-host-firewall.service`, since
  Ubuntu's `nftables.service` flushes the whole ruleset with libvirt's and podman's tables. It closes only the
  interfaces the default routes leave by, so the host's own bridges stay as they are.
- `porelo.host.lines` gave a meta task (`flush_handlers`, which the role needs to load the profile before the VPN
  comes up) a start and no end, and a handler an end and no start; both mended in the callback, with a test.

## Acceptance

- [x] On the test VM: a peer made for the test, in a network namespace of its own, reaches a service bound to every
  address through the VPN (`curl` 200); the same service is refused on the public address, from where Molecule
  connects, while ssh answers; `idempotence` reports `changed=0`; after `down` the interface and its file are gone.
  Seen red first: without the AppArmor rule `wg-quick@wg-porelo` does not start; without the firewall the service
  answers on the public address.
- [ ] The private key's value appears in no output of the run (`-vvv`) and in no file but its own. Checked so far:
  not in `up`'s lines; `-vvv` not yet.
- [ ] A missing key file stops the role before the firewall changes, naming the path. Built in `key.yml`, ahead of
  the firewall; not yet run.
