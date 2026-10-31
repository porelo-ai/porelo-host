# HO68 — SSH The Host's Only Way In

**Status:** Review.
**Size:** L - the vpn role's removal reaches up, down, the firewall, the stops and Molecule's converge and verify,
beside the sshd settings, the KRL and the person helper; L by the size rule (several modules and an acceptance step), no
measured L yet.
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
  refuses every key on a missing or broken one, and rebuilt by the sync into a new file renamed into place. Only a key
  the host admin's registry state names lost or stolen enters it, since a KRL refuses a key at every date: a key its
  owner replaced cleanly leaves `authorized_keys` and stays a `valid-before` signer for history, never in the KRL. A
  project admin's revocation of a lost key takes that key out of that project alone ([HO75](README.md#ho75)), and the
  pinned host admin's key is never revoked by a project.
- A host lock, the person's current key in the KRL, or the removal of their last membership also ends their sessions
  and user manager (`loginctl terminate-user`), so no open tunnel outlives it.
- Unix sockets are guarded by their file and directory modes alone, and the docs say so: the daemon's socket in
  `/run/user/<uid>/porelo` (0700), the services' sockets as their issues set them.
- Goes: the `vpn` role (WireGuard, `wg-porelo`, the address plan, its firewall rules), the `wireguard` stop.

## Acceptance

- no TCP listener for persons on the host after up (`ss -ltn`), only sshd on 22 from outside; an account outside
  `porelo-people` can forward no socket;
- a revoked key is refused at once and an expired card's key after its expiry; the KRL is never missing or half-written;
  the host admin logs in before the first sync;
- a project's revocation of a host admin's or another project's person's key leaves their host access as it was;
- a host lock ends a running tunnel; `-L` to another person's socket fails on its mode; `-A` and `-L` to a TCP port
  fail.

## Plan

- `roles/base`: a new `tasks/ssh.yml` writes `/etc/ssh/sshd_config.d/10-porelo-host.conf` (first value wins, so before
  Ubuntu's `50-cloud-init.conf`), validated with `sshd -t`, reloaded by a handler: the global forwarding limits, then
  `Match Group porelo-people` with `AllowStreamLocalForwarding all`, `StreamLocalBindUnlink yes`, `AuthorizedKeysFile
  /etc/ssh/authorized_keys/%u`. The person role's own drop-in (`roles/porelo/tasks/person.yml`) goes into it.
- `roles/base/tasks/firewall.yml` takes the firewall from `roles/vpn/tasks/firewall.yml` with only `tcp dport 22` open
  on the public interfaces; `templates/firewall.nft.j2` moves with it.
- KRL: `person.yml` seeds `/etc/ssh/porelo-revoked.krl` with `ssh-keygen -k -f` from an empty list where it is missing,
  and the drop-in names it. `porelo-host-person` gets `write_krl(keys)`, writing a new file with `ssh-keygen -k` and
  renaming it into place; [HO75](README.md#ho75) fills the keys.
- `porelo-host-person`: `admit` makes `/run/porelo-host/people/<login>/` (0700, the person's), `remove`/`purge` take it
  away; a tmpfiles line in `person.yml` makes it at boot for every recorded person. `lock` already ends the user's
  sessions in purge; `lock` gets the same `loginctl terminate-user` and `systemctl stop user@`. The authorized-keys line
  drops `from=` and gains `expiry-time=` ([HO75](README.md#ho75) gives the expiry; until then none).
- `playbooks/up.yml` and `down.yml` lose the `vpn` role and its `needs`; `porelo_host_needs` loses `wireguard`;
  `roles/vpn` is deleted, and `roles/base/tasks/down.yml` takes away a `wg-porelo` left by an earlier up.
  `roles/porelo/files/porelo-host-stop` loses `wireguard`; `doc/lines.md` with it.
- Molecule: converge feeds no `wireguard`; verify's VPN steps (test peer in a namespace on 10.73.7.0/24, Forgejo over
  the VPN) go, replaced by `ss -ltn` and a socket-forward check over ssh as a person; the full tunnel tests are
  [HO74](README.md#ho74)'s.
- Red first: `test_porelo_host_person.py` tests for the return directory at admit, its removal at purge,
  `terminate-user` at lock and the KRL written by rename.

## To be checked

- `ssh-keygen -k` with an empty input makes a KRL sshd accepts, on Ubuntu 26.04's OpenSSH 10.2.
- Whether the host admin, connecting as root for `up`, needs anything of the Match block (they do not forward sockets as
  root).
- Open from the readings, for after the test: the KRL's own validation, a root key with an options prefix, and the
  order of locks against a concurrent sync.
