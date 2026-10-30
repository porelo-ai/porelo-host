# HO71 — A Task Recorded And Given Its Forge Token By The Host

**Status:** Implementing.
**Size:** M - the host task/token API, private certificate records and daily sweep; measured M median 63 min,
from three M builds (47, 63, 75). The gate, stop and acceptance migration exceeds this host API boundary.
**Blocked by:** [HO70](README.md#ho70); Porelo's task certificate check.

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** Every forge token a person or task uses on the host is made by the host, never travels between
persons, and goes with the person or task; every task's certificate is recorded on the host at its start.

- At admit, the sync makes the person's own forge user and no token, since Forgejo keeps only a token's hash. `sudo
  porelo-host-person forge-token` makes the one token, with `write:repository` and `write:issue`, and answers it once
  on stdout to the person's own call through the tunnel; their Porelo keeps it in their vault, and it lies in no file.
  A new call replaces the old token.
- At a task's start, `sudo porelo-host-person task <task>` takes the task's certificate on stdin, bounded in size, uses
  OpenSSH to check that the person's current key signed it for that task, and records it append-only in root's
  `/var/lib/porelo-host/tasks/<login>/`. The host's task gate then holds a token for the person's agent forge user, made
  for that task and used only for the task's repository, and passes the task's branch on with it; the task never sees
  it. `task --end <task>` deletes it; a daily sweep deletes every task token whose recorded certificate has expired.
- `porelo-host-person task --show <fingerprint>` answers a recorded certificate, read-only, to any admitted person, so a
  plain-key signature is traced to its certificate after the task key is destroyed.
- A host lock, revocation of the person's current key in the applied registry, removal of their last membership, or
  purge deletes every token of the person's forge users, made by the host or not, and any password set on them.
- Goes: the `identities` stop and its `identities.tokens` files, the forge token kept in a file.

## Tests

- a certificate not signed by the person's key, or too long, is refused before anything is written; an expired task's
  token is gone after the sweep; a host lock leaves no token; the person's token is never in a file.

## Acceptance

- [ ] a certificate signed by another key, by the person's revoked key, for another task, not valid now, unsigned or
  longer than the bound is refused before anything is written, and no token is made;
- [ ] after the sweep, the token of a task whose recorded certificate has expired is gone and a running task's stays;
- [ ] a host lock, the removal of the last membership, a purge or the person's revocation in the registry leaves no
  token on any of the person's forge users;
- [ ] neither the person's token nor a task's is in any file, argv or diagnostic; admission makes none.

## Plan

- `roles/porelo/files/porelo-host-person` reads one Ed25519 user certificate from stdin, bounded at 16 KiB, through a
  private temporary file and `env TZ=UTC ssh-keygen -L -f`. Check its signature, finite validity, current time,
  principal `task:<task>` and signing CA against the caller's current, unrevoked `ssh` in the applied registry.
  Task names match `[a-z0-9][a-z0-9._-]{0,63}`; other principals and the key ID are recorded without interpretation.
- `task <task>` publishes root's 0600 `/var/lib/porelo-host/tasks/<login>/<task>.json` with `link(2)` in 0700
  directories. Record the canonical certificate, task key fingerprint, signer, principals, key ID and validity.
  Refuse replacement and ambiguous fingerprints; retrying the same certificate replaces only its token.
- Through the existing Forgejo command and TLS admin API, `forge-token` replaces every token of the person's login
  and answers one token alone on stdout. Admission creates users without tokens. A task gets a named token of
  `porelo-<login>` with `write:repository`; `task --end` deletes that token, leaving the certificate record.
  Person tokens also need `write:organization,read:user` for the existing bring, alongside repository and issue write.
- `task --show <fingerprint>` reads a certificate record for any unlocked admitted person or root. Root's `sweep`
  deletes tokens with expired recorded certificates and continues past one person's failure. The person role installs
  the daily persistent timer and checked sudo rules for the person-bound verbs.
- Registry revocation deletes all tokens of every forge user of the person after applying state, retrying on the next
  intake after a failure. Existing lock, last-membership removal and purge keep their all-token revocation paths.
- Red first: `tests/unit/roles/test_porelo_host_person_tasks.py` uses real OpenSSH keys and certificates and a fake
  Forgejo API. Cover foreign, revoked and rotated signers, wrong tasks, validity, malformed/bounded input, immutable
  records, links, replacement, end, show, sweep and revocation failure/retry. Update service tests for token-free admit.
- Remaining integration: replace the lasting vault credential in `roles/forge/tasks/gate.yml` with Porelo's task-start
  token handoff; replace the person's token-file path in `roles/forge/tasks/own.yml` with on-demand delivery. Remove
  the identities stop and update its callers in docs, tests and `extensions/molecule/default`. This needs a verified
  Porelo caller contract; no task-start hook exists in the current collection's gate setup.

## To be checked

- Confirm the certificate principal convention and task name shape with the Porelo producer. The host records person,
  project and repository principals as signed; it does not yet enforce their format or repository selection.
- Complete the gate's per-task credential handoff and repository restriction, including the build reader's credential.
  Forgejo's existing CLI here accepts API scopes, not a repository selector; verify the pinned server's narrowest
  token restriction before claiming that API scoping alone confines a token to one repository.
- Remove the identities stop, its files and all runtime-file consumers; migrate and run Molecule acceptance.
- Resolve the existing person's token file used temporarily by bring: the contract requires no token file.
- Run the pinned lint, full workflow, document checks and VM acceptance; obtain the required independent review.
