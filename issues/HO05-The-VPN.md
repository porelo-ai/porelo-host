# HO05 — The VPN

**Status:** Backlog.
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

## Acceptance

- On the test VM `build/molecule.sh` makes: a peer made for the test reaches the host through the VPN; the same service is refused on the public
  address; `idempotence` reports `changed=0`.
- The private key's value appears in no output of the run (`-vvv`) and in no file but its own.
- A missing key file stops the role before the firewall changes, naming the path.
