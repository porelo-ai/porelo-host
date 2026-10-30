# SSH access

The host's public interfaces accept SSH on TCP port 22. The base role installs
`/etc/ssh/sshd_config.d/10-porelo-host.conf` before cloud-init's drop-in, validates the daemon configuration and
reloads it before continuing. Password and keyboard-interactive authentication are disabled. Every account uses
`/etc/ssh/authorized_keys/%u`, owned by root, and `/etc/ssh/porelo-revoked.krl`. Setup must pin the host admin's key
in `/root/.ssh/authorized_keys` (or `base_host_admin_key_file`); up copies this file before changing SSH's key source.
A host admin handover replaces both the seed and the active root file. Installation seeds a valid empty KRL through
`ssh-keygen -k` and an atomic rename, without requiring registry synchronization. A later up preserves the KRL.

Agent forwarding, X forwarding and tunnels are disabled for every account, and so is all other forwarding except
for `porelo-people`. That group gets local and remote Unix socket forwarding with `StreamLocalBindUnlink yes` and keeps
its login shell. OpenSSH forwards no Unix socket while `AllowTcpForwarding` is `no`, and `PermitOpen none` refuses
socket paths as well, so the group also gets local TCP forwarding: it reaches only what the person's shell on the host
reaches anyway. `PermitListen none` refuses every remote TCP listener. sshd keeps the first value it reads, so both
forwarding keywords stand only in the `Match` blocks. A person's return socket belongs below
`/run/porelo-host/people/<login>/`, mode 0700, owned by that person. Admission creates the directory and an
`/etc/tmpfiles.d/porelo-person-<login>.conf` boot rule. The install step restores these for recorded people;
lock and purge remove both without following links in the person's writable directory.

OpenSSH has no per-path allowlist for Unix socket forwarding. Porelo must request its return socket in the person's
runtime directory; filesystem ownership and directory modes determine where the account can write. Unix sockets are
guarded by file and directory modes alone. In particular, the daemon directory `/run/user/<uid>/porelo` must be 0700;
service roles set their own socket permissions. Forwarding another person's socket fails when their directory is
private. SSH provides no extra path authorization layer.

## Registry input

The verified registry reader is a separate component. The `Host` class in the installed person helper exposes these
root-only integration calls; they consume already verified public input, never fetch or verify registry state:

- `write_authorized_key(login, key, expires=None)` atomically replaces one account's key file with one canonical
  Ed25519 public key, optionally prefixed with `expiry-time="YYYYMMDDHHMMSSZ"`. It accepts no source address
  restriction. The reader converts the card's expiry to UTC and supplies it here.
- `admit_runtime(login)` creates or validates the private runtime directory and writes its boot rule.
- `apply_ssh_revocations(keys, users)` takes the complete host-wide public-key revocation list and the affected
  account logins. It validates the inputs, atomically replaces the KRL via `write_krl(keys)`, then terminates every
  listed user's sessions and waits for their user manager to stop. All affected users are attempted on failure;
  a failed termination is reported and must be retried. Root is refused in the affected-user list.
- `end_sessions(login)` calls `loginctl terminate-user` and `systemctl stop user@<uid>.service`, and attempts both
  even if one fails. Existing `lock` and last-membership removal also perform these operations.

The reader holds the helper's existing configuration lock while reconciling. The install task invokes
`restore-runtime` under that same lock for existing unlocked member records. It supplies the complete affected-user
list for a KRL change; `write_krl` alone is a publication primitive and cannot infer users from public keys.
Only host admin registry revocations and key changes signed by the key owner enter this list. A project-scoped
revocation removes that project's membership alone; another membership preserves host access, and no project
operation calls the KRL writer or replaces the pinned host admin key.

The legacy add/sync input still reads laptop records pending card reconciliation. It no longer runs WireGuard or
publishes VPN peers; its SSH lines have no `from=` restriction. Those records have no card expiry, so the verified
card reader must call `write_authorized_key` with the expiry when admitting a card. The host admin's seeded key and
the empty KRL work before that reader exists.

## Verification

Unit fixtures cover key expiry validation, atomic KRL replacement, runtime directory ownership and boot rules, and
session termination. Molecule includes a real SSH Unix socket forward through an isolated account and a TCP listener
check. These require the installed host environment; a sandbox that cannot bind sockets cannot run the tunnel check.
The complete multi-service tunnel acceptance runs after the service roles and registry reader are integrated.
