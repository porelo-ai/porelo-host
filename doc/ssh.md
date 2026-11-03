# SSH access

The host's public interfaces accept SSH on TCP port 22. The base role installs
`/etc/ssh/sshd_config.d/10-porelo-host.conf` before cloud-init's drop-in, validates the daemon configuration and
reloads it before continuing. Password and keyboard-interactive authentication are disabled. Every account uses
`/etc/ssh/authorized_keys/%u`, owned by root, and `/etc/ssh/porelo-revoked.krl`. Setup must pin the host admin's key
in root's `authorized_keys` in the SSH folder (or `base_host_admin_key_file`); up adds its key before changing SSH's key source.
A follow replaces root's active key file with the organization's current host admin keys, and a host admin handover
takes effect at that follow. The Organization Admins' keys stand in the pin, not in root's file: one who needs root lists
themselves as that machine's admin, a signed change anyone can read. Before the first follow each `up` adds the seed to the keys there and removes none, so
another key that already reaches root keeps its way in. After a follow `up` leaves the file to the follow, and
a host admin it replaced does not come back with an old seed.
Installation seeds a valid empty KRL through
`ssh-keygen -k` and an atomic rename, without requiring organization synchronization. A later up preserves the KRL.

Agent forwarding, X forwarding and tunnels are disabled for every account, and so is all other forwarding except
for `porelo-people`. That group gets local and remote Unix socket forwarding with `StreamLocalBindUnlink yes` and keeps
its login shell. OpenSSH forwards no Unix socket while `AllowTcpForwarding` is `no`, and `PermitOpen none` refuses
socket paths as well, so the group also gets local TCP forwarding: it reaches only what the person's shell on the host
reaches anyway. `PermitListen none` refuses every remote TCP listener. sshd keeps the first value it reads, so both
forwarding keywords stand only in the `Match` blocks. A person's return socket is
`/run/porelo-host/people/<login>/return.sock`, in a directory of mode 0700 owned by that person. Beside it,
`porelod.sock` links to the person's daemon at `/run/user/<uid>/porelo/porelod.sock`, so the tunnel forwards to a name
known from the login alone. Admission creates the directory, the link and an
`/etc/tmpfiles.d/porelo-person-<login>.conf` boot rule for both; a person's own entry at the link's name stays. The install step restores these for recorded people;
lock and purge remove both without following links in the person's writable directory.

OpenSSH has no per-path allowlist for Unix socket forwarding. Porelo must request its return socket in the person's
runtime directory; filesystem ownership and directory modes determine where the account can write. Unix sockets are
guarded by file and directory modes alone. In particular, the daemon directory `/run/user/<uid>/porelo` must be 0700;
service roles set their own socket permissions. Forwarding another person's socket fails when their directory is
private. SSH provides no extra path authorization layer.

## Organization input

The verified organization reader is a separate component. The `Host` class in the installed person helper exposes these
root-only integration calls; they consume already verified public input, never fetch or verify organization state:

- `write_authorized_key(login, key, expires=None)` atomically replaces one account's key file with one canonical
  Ed25519 public key, optionally prefixed with `expiry-time="YYYYMMDDHHMMSSZ"`. It accepts no source address
  restriction. The reader converts the card's expiry to UTC and supplies it here.
- `admit_runtime(login)` creates or validates the private runtime directory and the `porelod.sock` link in it, leaving a
  person's own entry at that name, and writes their boot rule.
- `apply_ssh_revocations(keys, users)` takes the complete host-wide public-key revocation list and the affected
  account logins. It validates the inputs, atomically replaces the KRL via `write_krl(keys)`, then terminates every
  listed user's sessions and waits for their user manager to stop. All affected users are attempted on failure;
  a failed termination is reported and must be retried. Root is refused in the affected-user list.
- `end_sessions(login)` calls `loginctl terminate-user` and `systemctl stop user@<uid>.service`, and attempts both
  even if one fails. A lock from the follow, a revoked key or the last membership lost, performs these operations too.

The reader holds the helper's existing configuration lock while reconciling. The install task invokes
`restore-runtime` under that same lock for existing unlocked member records. It supplies the complete affected-user
list for a KRL change; `write_krl` alone is a publication primitive and cannot infer users from public keys.
Only host admin organization revocations and key changes signed by the key owner enter this list. A project-scoped
revocation removes that project's membership alone; another membership preserves host access, and no project
operation calls the KRL writer or replaces the pinned host admin key.

The follow reads each person's current card key and expiry from the verified organization and supplies the expiry
to `write_authorized_key`. The host admin's seeded key and the empty KRL provide access before the first follow.

## Verification

Unit fixtures cover key expiry validation, atomic KRL replacement, runtime directory ownership and boot rules, and
session termination. Molecule includes a real SSH Unix socket forward through an isolated account and a TCP listener
check. These require the installed host environment; a sandbox that cannot bind sockets cannot run the tunnel check.
The complete multi-service tunnel acceptance runs after the service roles and organization reader are integrated.
