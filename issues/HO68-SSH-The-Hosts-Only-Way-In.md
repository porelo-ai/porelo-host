# HO68 — SSH The Host's Only Way In

**Status:** Accepted (operator, 2026-10-30, with the project's one-click joining).
**Size:** M - the vpn role out, the firewall down to port 22, sshd's settings and the KRL, with unit tests and a VM run;
measured M median 63 min, from three M builds (47, 63, 75).
**Blocked by:** [HO70](README.md#ho70).

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** A person reaches the host only over SSH on port 22, with the one key of their card, from any
machine. Nothing else on the host answers from outside, and nothing on it listens on TCP for persons.

- sshd, for every account, the host admin's included: `AllowTcpForwarding no`, `AllowAgentForwarding no`, `X11Forwarding
  no`, `PermitTunnel no`, so no KeePassXC agent ever reaches the host or a task.
- `Match Group porelo-people`: `AllowStreamLocalForwarding all`, local for the services' and the daemon's sockets,
  remote for the one return socket; `StreamLocalBindUnlink yes`; the login shell stays, for the account's own Porelo,
  `porelo daemon connect` and `git-upload-pack`.
- The one return socket lies in `/run/porelo-host/people/<login>/` (0700, the person's, made at boot by tmpfiles) and is
  read only by the person's own processes. sshd has no per-path list for socket forwards, so that `ssh -R` goes only
  there rests on Porelo's own call and on where the account may write; the docs say so.
- `AuthorizedKeysFile /etc/ssh/authorized_keys/%u`, written by the sync from the card's key alone with `expiry-time`
  from the card's `expires`, no `from=`. `RevokedKeys /etc/ssh/porelo-revoked.krl`, seeded empty at install, since sshd
  refuses every key while it is missing, and rebuilt at each sync from the revocations the registry and the access files
  carry.
- A lock, a revocation or a removal also ends the person's running sessions and user manager (`loginctl
  terminate-user`), so no open tunnel outlives it.
- Unix sockets are guarded by their file and directory modes alone, and the docs say so: the daemon's socket in
  `/run/user/<uid>/porelo` (0700), the services' sockets as their issues set them.
- Goes: the `vpn` role (WireGuard, `wg-porelo`, the address plan, its firewall rules), the `wireguard` stop.

## Tests

- no TCP listener for persons on the host after up (`ss -ltn`), only sshd on 22 from outside;
- a revoked key is refused at once, an expired card's key after its expiry, and a missing KRL file is never left;
- a lock ends a running tunnel; `-L` to another person's socket fails on its mode; `-A` and `-L` to a TCP port fail.
