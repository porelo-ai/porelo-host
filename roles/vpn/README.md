# vpn

The person's VPN to the host: WireGuard on `vpn_interface`, to the peers the inventory names, and a firewall that
leaves only ssh and the VPN's UDP port on the public interfaces, those the default routes leave by. Everything else
the host offers is reached through the VPN or the host's own bridges. The firewall is an nftables table of its own,
`inet porelo_host`, loaded by `porelo-host-firewall.service`, so libvirt's and podman's tables stay as they are.

The host's private key never passes through Ansible: the interface's file names its path in a `PostUp`, and `wg`
reads it. The role checks the file is there and lets Ubuntu's AppArmor profile for `wg` read that one file.

`tasks_from: down` stops the interface and removes its file.

## Requirements

Ubuntu 26.04, run as root on the host itself (`-c local`), after the drive is synced, since the key is on it.

## Variables

| Variable | Default | What it is |
|---|---|---|
| `vpn_interface` | `wg-porelo` | The VPN's interface. |
| `vpn_port` | `51820` | The UDP port the VPN listens on. |
| `vpn_address` | (required) | The host's address inside the VPN with its prefix. |
| `vpn_peers` | (required) | The person's peers, each `public_key` and `allowed_ips`. |
| `vpn_private_key_path` | (required) | The file on the person's drive holding the host's private key. |
| `vpn_ssh_port` | `22` | The TCP port ssh listens on, kept open on the public address. |

## Example

    - name: Bring the host up
      hosts: localhost
      connection: local
      roles:
        - role: porelo.host.vpn
          vars:
            vpn_address: 10.73.0.1/24
            vpn_private_key_path: /srv/porelo-host/drive/host/wireguard.key
            vpn_peers:
              - public_key: "<the person's public key>"
                allowed_ips: 10.73.0.2/32

## Behaviour

**Idempotent**: a second run changes nothing, measured by Molecule's idempotence step. **Check mode** is not tested.
**Rollback** is not offered; `down` stops the VPN, and the firewall goes with the host.

## License

GPL-3.0-or-later.
