# HO42 — The Host Prepared With No Project Or Person

**Status:** Estimated (Accepted and Estimated by the operator, 2026-10-28).
**Size:** L - `up` reduced to the host's own parts, the Matrix homeserver moved to an account of the host's, the
host admin's constrained CA for two names, a VPN network per host, and the Molecule scenario's first act.

**What must be true.** The host admin prepares a host once, as root, with no project and no person: the VPN, the
forge, the runner, the VM pool and a Matrix homeserver, shared by every person later admitted, reached under the
host's own names with certificates of the host admin's lasting CA.

## Why

[PJ78](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj78), the operator's split of a host's life into three roles. Today `up` brings one person's project up with the host
in one run; the forge, runner, pool and homeserver are the host's and shared (QH56), so they come first and alone.

## Plan

Read in the code (`9f883ec`), nothing measured.

- **`up` keeps:** base and Porelo's packages; the VPN interface `10.73.<n>.1/24`, `<n>` given by the host admin's
  interface (QH66 a); the forge's accounts, service and admin; the runner; the VM pool.
- **`up` loses:** Porelo's account and vault, the project step, the agents' install, the person's login. They move
  to [HO43](README.md#ho43) and [HO45](README.md#ho45).
- **The homeserver:** an account of its own, `porelo-matrix` (linger), with `PORELO_MATRIX_PORT` in its
  `homeserver.conf`, its user unit enabled by `up`, and `publish --address <VPN address>:<port> --name
  matrix.<host>.porelo.internal`, as porelo-message-matrix's [MX42](https://github.com/porelo-ai/porelo-message-matrix/blob/main/issues/README.md#mx42) run did. No task starts it and no person's
  `vault clear` reaches it; `down` stops it and removes its account.
- **Certificates:** the forge's and the homeserver's, `forge.<host>.porelo.internal` and
  `matrix.<host>.porelo.internal`, signed by the host admin's lasting CA (QH58 a), constrained to
  `*.<host>.porelo.internal` and `10.73.<n>.0/24`. [HO35](README.md#ho35)'s request, `--request` and
  `forge-certificate` checks stay; the constraint they check becomes the host's names and network.
- **The root stop** asks only `wireguard` and `forge-certificate`.
- **`up` ends by printing** what a project's `host:` block in `access.yml` needs: address, endpoint, WireGuard public
  key, network, ssh host key fingerprint, the CA's SHA-256, and the homeserver's name.

## Acceptance

- Molecule: `up` with no project and no person ends green; the forge, runner and homeserver answer on the VPN address
  under their names, each certificate verifying under the stand-in host CA and failing for a name outside
  `<host>.porelo.internal`; no Porelo account exists; the printed values equal the host's own.
- The root stop refuses every need but `wireguard` and `forge-certificate`.
- `down` leaves no account, unit or volume of the forge, runner or homeserver.

## To be checked

- That the homeserver's user unit under `porelo-matrix` survives a reboot with linger, as the forge's does.

## The operator's correction, 2026-10-28

The host's own forge is optional: on by default when the host is prepared, and switched off there where the people use
a central forge. Then nothing of a forge is set up on the host, and a project put on it brings nothing into a local one.
`porelo_host_forge` keeps its default off in porelo-host; the interface writes the person's choice. The person's login
and password script come with the forge itself ([HO49](README.md#ho49)), not with repositories.
