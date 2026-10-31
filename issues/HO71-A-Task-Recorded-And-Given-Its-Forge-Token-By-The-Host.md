# HO71 — A Task Recorded And Given Its Forge Token By The Host

**Status:** Review.
**Size:** M - the host task/token API, private certificate records and daily sweep; measured M median 63 min,
from three M builds (47, 63, 75).
**Blocked by:** [HO70](README.md#ho70); Porelo's task certificate check.

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** Every forge token a person or task uses on the host is made by the host, never travels between
persons, and goes with the person or task; every task's certificate is recorded on the host at its start.

- At admit, the sync makes the person's own forge user and no token, since Forgejo keeps only a token's hash. `sudo
  porelo-host-person forge-token` makes the one token, with `write:repository`, `write:issue`, `write:organization`
  and `read:user`, and answers it once on stdout to the person's own call. Bring and join call it at each run and put
  the answer into the person's vault entry `<forge>.person` at once; for the play's own forge calls it lies in a 0600
  file in the person's runtime directory on tmpfs, removed at the play's end. A new call replaces the old token.
- At a task's start, `sudo porelo-host-person task <task>` takes the task's certificate on stdin, bounded in size,
  checks with OpenSSH that the person's current key signed it with the one principal `task:<project>:<task>` of a
  project the person is a member of, has Porelo's `task check-certificate` judge the same certificate against that key
  and the KRL, and records it append-only in root's `/var/lib/porelo-host/tasks/<login>/`. It answers a token of the
  person's agent forge user `porelo-<login>` made for that task, which Porelo's gate keeps in the task's vault entry
  and pushes the task's branch with. `task --end <task>` deletes it; a daily sweep deletes every task token whose
  recorded certificate has expired.
- `porelo-host-person task --show <fingerprint>` answers a recorded certificate, read-only, to any admitted person, so a
  plain-key signature is traced to its certificate after the task key is destroyed.
- A host lock, revocation of the person's current key in the applied registry, removal of their last membership, or
  purge deletes every token of the person's forge users, made by the host or not, and any password set on them.
- Goes: the `identities` stop and its `identities.tokens` files, and the forge role's lasting gate token.

## Tests

- a certificate not signed by the person's key, for a project the person is no member of, refused by Porelo's check,
  or too long, is refused before anything is written; an expired task's token is gone after the sweep; a host lock
  leaves no token; the person's token is in no file but the play's own on tmpfs.

## Acceptance

- [ ] a certificate signed by another key, by the person's revoked key, for another task or a project the person is no
  member of, not valid now, unsigned or longer than the bound is refused before anything is written, and no token is
  made;
- [ ] after the sweep, the token of a task whose recorded certificate has expired is gone and a running task's stays;
- [ ] a host lock, the removal of the last membership, a purge or the person's revocation in the registry leaves no
  token on any of the person's forge users;
- [ ] no token is in an argv or diagnostic, a task's in no file, the person's in no file but the play's own on tmpfs;
  admission makes none.

## Plan

- `roles/porelo/files/porelo-host-person` reads one Ed25519 user certificate from stdin, bounded at 16 KiB, through a
  private temporary file and `env TZ=UTC ssh-keygen -L -f`. Check its signature, finite validity, current time, the
  one principal `task:<project>:<task>` (or `task:default:<task>`), the caller's membership of that project and the
  signing CA against the caller's current, unrevoked `ssh` in the applied registry. Task names match
  `[a-z0-9][a-z0-9._-]{0,63}`.
- Then `porelo task check-certificate --task --login --keys --krl --json` runs in a `systemd-run` unit with a dynamic
  user, no network and no home, given the key in force and a descriptor-read copy of `/etc/ssh/porelo-revoked.krl` as
  credentials and the certificate on stdin. Its answer must name the same task key, signer and project.
- `task <task>` publishes root's 0600 `/var/lib/porelo-host/tasks/<login>/<task>.json` with `link(2)` in 0700
  directories. Record the canonical certificate, task key fingerprint, signer, principals, key ID and validity.
  Refuse replacement and ambiguous fingerprints; retrying the same certificate replaces only its token.
- Through the forge's private socket API, `forge-token` replaces every token of the person's login and answers one
  token alone on stdout. Admission creates users without tokens. A task gets a named token of `porelo-<login>` with
  `write:repository`; `task --end` deletes that token, leaving the certificate record. Forgejo scopes a token by API
  scope, not by repository: Porelo's gate pushes only the certified repository's branch, but the token alone reaches
  every repository `developers` writes.
- `task --show <fingerprint>` reads a certificate record for any unlocked admitted person or root. Root's `sweep`
  deletes tokens with expired recorded certificates and continues past one person's failure. The person role installs
  the daily persistent timer and checked sudo rules for the person-bound verbs.
- Registry revocation deletes all tokens of every forge user of the person after applying state, retrying on the next
  intake after a failure. Existing lock, last-membership removal and purge keep their all-token revocation paths.
- `roles/forge/tasks/own.yml` takes the person's token from `forge-token` into the vault and the play's file;
  `roles/forge/tasks/gate.yml`, `forge_porelo_account` and the `identities` stop go. A bring with no file at all is
  [HO82](README.md#ho82). Molecule's people, projects, bring, push and two-projects tasks still read identities tokens;
  they are skipped (`notest`) and rewritten with [HO74](README.md#ho74).
- Red first: `tests/unit/roles/test_porelo_host_person_tasks.py` uses real OpenSSH keys and certificates, a stand-in
  for Porelo's check and a fake Forgejo API. Cover foreign, revoked and rotated signers, wrong tasks, projects and
  memberships, Porelo's refusal or another answer, the KRL missing, linked or writable, validity, malformed/bounded
  input, immutable records, links, replacement, end, show, sweep and revocation failure/retry.
