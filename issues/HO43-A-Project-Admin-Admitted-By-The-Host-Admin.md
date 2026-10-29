# HO43 — A Project Admin Admitted By The Host Admin

**Status:** Estimated.
**Size:** L - a root helper with its records, two sudoers lines, an account with its keys, VPN peers and forge
identities, the Matrix token, the lock and the purge.

**What must be true.** The host admin admits a project admin to a prepared host from the person's public keys alone,
and removes them again; each person on the host has their own account, laptops, forge login and identities, and no
person can change another's.

## Why

The host admin puts the project admins' public keys on the host by hand; developers then follow from the
project's signed `access.yml` ([HO46](README.md#ho46)), through the same helper.

## Plan

- **`/usr/local/sbin/porelo-host-person`**, root (`python3 -I`, environment cleared), with root's records in
  `/etc/porelo-host/`: `people/<user>.conf` (role, projects, laptops and their keys and addresses) and
  `projects/<project>.conf` (written by [HO44](README.md#ho44)).
- **`add <user> --role project-admin`**, public keys on standard input (the person's *Copy my public keys*):
  - the account by `porelo-setup.sh --user`, with KVM and libvirt groups;
  - per laptop, the ssh key in `/etc/ssh/authorized_keys/<user>` (root's) and a VPN peer at its address;
  - the forge login; the gate's and agents' identities `porelo-<user>` and `<agent>-<user>`, their tokens in a
    `0600` `identities.tokens` in the person's own `0700` `/run/porelo-host/people/<user>/`, under root's `0755`
    `people` directory, for the person's own act to pipe into their own vault and remove; links and a directory not
    owned by the person are refused, and lock and purge remove the delivery directory without following its links;
  - the Matrix token, `machine-token issue <host>-<user>` (QB77 a) run as `porelo-matrix`, into the person's
    `~/.config/porelo/matrix/host-registration-token`, `0600` in a `0700` directory.
- **Lock** (a person in no project any more, QH65 a): the ssh keys and peers out, the forge login disabled, their
  tasks stopped (`task stop --all`), `machine-token expel` expelling the accounts and revoking registration together.
  Exit 78 with case-insensitive `knows nothing` on stderr means there is no machine to take away; another refusal
  stops with its own words. **`purge <user>`**, the host admin's only:
  `vault clear`, then the account.
- **Sudoers:** each person may run `porelo-host-forge-password` for their own login only, taken from `SUDO_USER`;
  project admins may also run `porelo-host-person sync` ([HO46](README.md#ho46)).
- **Refusals,** every one before anything changes: an account outside the pattern; an existing account that is no
  person of the records; keys or addresses differing from those recorded; an address outside the network or taken.
- It prints names and addresses only, never a token.

## The contract with the interface

- **Standard input of `add`:** one laptop per line, `<laptop> <ssh-ed25519 AAAA…> <WireGuard public key>`, fields
  separated by one space and no comment; `<laptop>` matches `^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$`, the WireGuard key is
  44 base64 characters ending in `=`. An optional fourth field `10.73.<n>.<m>` asks for that address; without it the
  host takes the lowest free one from `.2` up, past the host admin's own. A laptop already recorded keeps its address.
- **On success** one JSON line on stdout: `add <user> --role project-admin` answers
  `{"person":"<user>","role":"project-admin","laptops":[{"laptop":"…","vpn_address":"10.73.<n>.<m>"}]}`, `lock <user>`
  `{"person":"<user>","locked":true}`, `purge <user>` `{"person":"<user>","purged":true}`.
- **A refusal** goes to stderr as `porelo-host-person: <words>`, with nothing changed and exit 64 (input), 65 (the
  records say no), 69 (something needed is missing or not root's) or 73 (cannot write).
- The interface runs it as `ssh root@10.73.<n>.1 /usr/local/sbin/porelo-host-person …` with the rental's key.

## Acceptance

- Molecule: a project admin added from a key block reaches the host over ssh only through the VPN with that laptop's
  key; their vault takes the identities' tokens from the `/run` file, which is then gone; their Porelo registers on
  the host's homeserver as `<host>-<user>`; locked, none of it works and their tasks are stopped; purged, the account
  is gone. Each refusal seen red first, and no token in any output, file but its own, or the journal.

## To be checked

- That porelo-message-matrix's verbs, run as `porelo-matrix`, answer on stdout only: `machine-token issue M` with
  `{"machine":"M","token":"…"}`, the same token again for a person already admitted; `expel M` with
  `{"machine":"M","expelled":[…],"revoked":true|false}`, every `@….<M>` account taken out server-wide and its
  registration token revoked together, so the homeserver refuses it at the next registration. Expelling a machine
  with no token, record or account exits 78.
- That the unknown-machine refusal actually includes `knows nothing`; the case-insensitive text match is a guess
  to confirm against the homeserver's stderr, since it has no distinct refusal code.
- That Porelo names a transport's machine `<host>-<account>` (`porelo talk machine` prints it).
