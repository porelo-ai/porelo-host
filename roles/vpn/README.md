# vpn

The person's VPN to the host: WireGuard on `vpn_interface`, to the peers the inventory names, and a firewall that
leaves only ssh and the VPN's UDP port on the public interfaces, those the default routes leave by. Everything else
the host offers is reached through the VPN or the host's own bridges. The firewall is an nftables table of its own,
`inet porelo_host`, loaded by `porelo-host-firewall.service`, so libvirt's and podman's tables stay as they are.

The host's private key never passes through Ansible: the person's stop (`porelo-host-stop --stdin wireguard`, run as
root) writes it from the person's secrets file into `vpn_private_key_path`, root's alone with mode `0600`, the
interface's file names that path in a `PostUp`, and `wg` reads it at every start of the interface, so a reboot keeps
the VPN. The role checks the file is root's alone and refuses otherwise, naming `wireguard`. The key lies in the clear
on the host's disk, an accepted risk ([decisions](../../doc/decisions.md#the-hosts-vpn-key-on-its-disk)).

`tasks_from: needs`, in `up`'s first play, writes the key's path into `/etc/porelo-host/vpn.conf` for the stop and
adds `wireguard` to `porelo_host_needs` while neither the key's file nor the interface is there. `tasks_from: down`
stops the interface and removes its file, the key and `vpn.conf`.

## Requirements

Ubuntu 26.04, run as root on the host itself (`-c local`), after the person's stop has given the key.

## Variables

| Variable | Default | What it is |
|---|---|---|
| `vpn_interface` | `wg-porelo` | The VPN's interface. |
| `vpn_port` | `51820` | The UDP port the VPN listens on. |
| `vpn_address` | `10.73.0.1/24` | The host's address inside the VPN with its prefix. |
| `vpn_peers` | the one peer of `porelo_host_vpn_peer_public_key` and `porelo_host_vpn_peer_address` | The person's peers, each `public_key` and `allowed_ips`. |
| `vpn_private_key_path` | `/etc/wireguard/porelo-host.key` | The file holding the host's private key, written by the person's stop. |
| `vpn_ssh_port` | `22` | The TCP port ssh listens on, kept open on the public address. |

## Example

    - name: Bring the host up
      hosts: localhost
      connection: local
      roles:
        - role: porelo.host.vpn
          vars:
            porelo_host_vpn_peer_public_key: "<the person's public key>"
            porelo_host_vpn_peer_address: 10.73.0.2/32

## Behaviour

**Idempotent**: a second run changes nothing, measured by Molecule's idempotence step. **Check mode** is not tested.
**Rollback** is not offered; `down` stops the VPN, and the firewall goes with the host.

## License

GPL-3.0-or-later.
