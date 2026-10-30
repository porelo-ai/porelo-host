# HO68 — SSH The Host's Only Way In

**Status:** Accepted (operator, 2026-10-30, with the project's one-click joining).
**Size:** M - the vpn role out, the firewall down to port 22, sshd's settings and the KRL, with unit tests and a VM run;
measured M median 63 min, from three M builds (47, 63, 75).
**Blocked by:** [HO70](README.md#ho70).

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** A person reaches the host only over SSH on port 22, with the one key of their card, from any
machine. Nothing else on the host answers from outside, and nothing on it listens on TCP for persons.

- sshd, for every account: `AllowTcpForwarding no`, `AllowAgentForwarding no`, `X11Forwarding no`, `PermitTunnel no`,
  `AllowStreamLocalForwarding no`, so no KeePassXC agent ever reaches the host or a task. `Match Group porelo-people`
  alone opens `AllowStreamLocalForwarding all`, local for the services' and the daemon's sockets, remote for the one
  return socket, with `StreamLocalBindUnlink yes`; the login shell stays, for the account's own Porelo, `porelo daemon
  connect` and `git-upload-pack`.
- The one return socket lies in `/run/porelo-host/people/<login>/` (0700, the person's): the sync makes it at admit and
  removes it at removal and purge, and tmpfiles makes it again at boot. sshd has no per-path list for socket forwards,
  so that `ssh -R` goes only there rests on Porelo's own call and on where the account may write; the docs say so.
- `AuthorizedKeysFile /etc/ssh/authorized_keys/%u`, written by the sync from the card's key alone with `expiry-time`
  from the card's `expires`, no `from=`. `up` seeds the host admin's file from the key pinned at setup, and a host
  admin's handover replaces it, so the host admin is never locked out before or between syncs.
- `RevokedKeys /etc/ssh/porelo-revoked.krl`: seeded at install as a valid empty KRL made by `ssh-keygen -k`, since sshd
  refuses every key on a missing or broken one, and rebuilt by the sync into a new file renamed into place. Only a
  revocation by the host admin's registry state, or a key change signed by the key's own owner, enters it; a project
  admin's revocation of a lost key takes that key out of that project alone ([HO75](README.md#ho75)), and the pinned
  host admin's key is never revoked by a project.
- A host lock, a revocation in the KRL, or the removal of a person's last membership also ends their running sessions
  and user manager (`loginctl terminate-user`), so no open tunnel outlives it.
- Unix sockets are guarded by their file and directory modes alone, and the docs say so: the daemon's socket in
  `/run/user/<uid>/porelo` (0700), the services' sockets as their issues set them.
- Goes: the `vpn` role (WireGuard, `wg-porelo`, the address plan, its firewall rules), the `wireguard` stop.

## Tests

- no TCP listener for persons on the host after up (`ss -ltn`), only sshd on 22 from outside; an account outside
  `porelo-people` can forward no socket;
- a revoked key is refused at once and an expired card's key after its expiry; the KRL is never missing or half-written;
  the host admin logs in before the first sync;
- a project's revocation of a host admin's or another project's person's key leaves their host access as it was;
- a host lock ends a running tunnel; `-L` to another person's socket fails on its mode; `-A` and `-L` to a TCP port
  fail.
