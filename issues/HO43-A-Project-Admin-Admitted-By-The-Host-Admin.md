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
    `0600` file of the person's on `/run`, for the person's own act to pipe into their own vault;
  - the Matrix token, `machine-token issue <host>-<user>` (QB77 a) run as `porelo-matrix`, into the person's
    `~/.config/porelo/matrix/host-registration-token`, `0600` in a `0700` directory.
- **Lock** (a person in no project any more, QH65 a): the ssh keys and peers out, the forge login disabled, their
  tasks stopped (`task stop --all`), `machine-token expel` then `revoke`. **`purge <user>`**, the host admin's only:
  `vault clear`, then the account.
- **Sudoers:** each person may run `porelo-host-forge-password` for their own login only, taken from `SUDO_USER`;
  project admins may also run `porelo-host-person sync` ([HO46](README.md#ho46)).
- **Refusals,** every one before anything changes: an account outside the pattern; an existing account that is no
  person of the records; keys or addresses differing from those recorded; an address outside the network or taken.
- It prints names and addresses only, never a token.

## Acceptance

- Molecule: a project admin added from a key block reaches the host over ssh only through the VPN with that laptop's
  key; their vault takes the identities' tokens from the `/run` file, which is then gone; their Porelo registers on
  the host's homeserver as `<host>-<user>`; locked, none of it works and their tasks are stopped; purged, the account
  is gone. Each refusal seen red first, and no token in any output, file but its own, or the journal.

## To be checked

- That porelo-message-matrix's verbs, run as `porelo-matrix`, answer on stdout only: `machine-token issue M` with
  `{"machine":"M","token":"…"}`, the same token again for a person already admitted; `revoke M` with
  `{"machine":"M","revoked":true|false}`, after which the homeserver refuses the token at its next registration;
  `expel M` with `{"machine":"M","expelled":[…]}`, every `@….<M>` account taken out server-wide, run before `revoke`.
- That Porelo names a transport's machine `<host>-<account>` (`porelo talk machine` prints it).
