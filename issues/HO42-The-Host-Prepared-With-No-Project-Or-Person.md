# HO42 — The Host Prepared With No Project Or Person

**Status:** Implementing.
**Size:** L - `up` reduced to the host's own parts, the Matrix homeserver moved to an account of the host's, the
host admin's constrained CA for two names, a VPN network per host, and the Molecule scenario's first act.

**What must be true.** The host admin prepares a host once, as root, with no project and no person: the VPN, the
forge, the runner, the VM pool and a Matrix homeserver, shared by every person later admitted, reached under the
host's own names with certificates of the host admin's lasting CA.

## Why

A host's life splits into three roles: the host admin, a project admin and a developer. Today `up` brings one person's project up with the host
in one run; the forge, runner, pool and homeserver are the host's and shared (QH56), so they come first and alone.

## Plan

Read in the code (`9f883ec`), nothing measured.

- **`up` keeps:** base and Porelo's packages; the VPN interface `10.73.<n>.1/24`, `<n>` given by the host admin's
  interface (QH66 a); the forge's accounts, service and admin; the runner; the VM pool.
- **`up` loses:** Porelo's account and vault, the project step, the agents' install, the person's login. They move
  to [HO43](README.md#ho43) and [HO45](README.md#ho45).
- **The homeserver:** an account of its own, `porelo-matrix` (linger), with `PORELO_MATRIX_PORT` in its
  `homeserver.conf`, its user unit enabled by `up`, and `publish --address <VPN address>:<port> --name
  matrix.<host>.porelo.internal`. No task starts it and no person's
  `vault clear` reaches it; `down` stops it and removes its account.
- **Certificates:** the forge's and the homeserver's, `forge.<host>.porelo.internal` and
  `matrix.<host>.porelo.internal`, signed by the host admin's lasting CA (QH58 a), constrained to
  `*.<host>.porelo.internal` and `10.73.<n>.0/24`. [HO35](README.md#ho35)'s request, `--request` and
  `forge-certificate` checks stay; the constraint they check becomes the host's names and network.
- **The root stop** asks only `wireguard` and `forge-certificate`.
- **`up` ends by printing** what a project's `host:` block in `access.yml` needs: address, endpoint, WireGuard public
  key, network, ssh host key fingerprint, the CA's SHA-256, and the homeserver's name.

## The contract with the interface

- **The inventory, `porelo_host_inventory_version: 2`:** `porelo_host_name` (`<host>`, one DNS label
  `^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$`), `porelo_host_network` (`<n>`, an integer from 0 to 255; the host is
  `10.73.<n>.1/24`), `porelo_host_distribution`, `porelo_host_vpn_peer_public_key`, `porelo_host_vpn_peer_address` (the
  host admin's laptop, in `10.73.<n>.0/24`, not `.1`) and `porelo_host_forge`. No account, project or authorized key:
  the host admin works as root with the rental's key. Any other version is refused, naming it.
- **`porelo-host-stop --request`** prints two PEM requests, the forge's then the homeserver's, `CN=forge.<host>.porelo.internal`
  and `CN=matrix.<host>.porelo.internal`. The interface takes only the key from each and signs it with
  `subjectAltName=DNS:<its CN>,IP:10.73.<n>.1`, `basicConstraints=critical,CA:FALSE`, `keyUsage=critical,digitalSignature`, `extendedKeyUsage=serverAuth`.
- **`forge-certificate <base64>`** is `base64 -w0` of three PEM certificates joined by newlines: the forge's, the
  homeserver's, the CA's. The CA carries critically `permitted;DNS:<host>.porelo.internal` and
  `permitted;IP:10.73.<n>.0/255.255.255.0` and nothing else, and on a later run is the CA already there. Each refusal
  names the certificate it is about.
- **At its end `up` gives** one line of the lines callback, `{"v": 1, "state": "host", "host": {…}}`, and writes the
  same object, `0644`, to `/etc/porelo-host/host.json`: `address` (public IPv4), `endpoint` (`<address>:51820`), `wireguard_public_key`, `network`
  (`10.73.<n>.0/24`), `ssh_host_key` (`ssh-ed25519 …`), `ca_sha256` (64 lower-case hex digits of the CA's DER) and
  `homeserver` (`matrix.<host>.porelo.internal`).
- **The homeserver** (`porelo-matrix`): porelo-host writes `PORELO_MATRIX_PORT` and `PORELO_MATRIX_SERVER_NAME` into
  `~/.config/porelo/matrix/homeserver.conf` before the first start, and places `ca.crt` (`0644`), `tls/server.crt`
  and `tls/server.key` (`0600`, `tls/` `0700`) beside it, owned by the account and with no `ca.key`; `publish` keeps them
  while they verify, fit and name its address and name. That last part waits on the homeserver serving a certificate
  made elsewhere.

## Acceptance

- Molecule: `up` with no project and no person ends green; the forge, runner and homeserver answer on the VPN address
  under their names, each certificate verifying under the stand-in host CA and failing for a name outside
  `<host>.porelo.internal`; no Porelo account exists; the printed values equal the host's own.
- The root stop refuses every need but `wireguard` and `forge-certificate`.
- `down` leaves no account, unit or volume of the forge, runner or homeserver.

## To be checked

- That the homeserver's user unit under `porelo-matrix` survives a reboot with linger, as the forge's does.

## The host's own forge is optional

It is on by default when the host is prepared, and switched off there where the people use
a central forge. Then nothing of a forge is set up on the host, and a project put on it brings nothing into a local one.
`porelo_host_forge` keeps its default off in porelo-host; the interface writes the person's choice. The person's login
and password script come with the forge itself ([HO49](README.md#ho49)), not with repositories.
