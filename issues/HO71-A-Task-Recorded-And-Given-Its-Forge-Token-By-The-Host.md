# HO71 — A Task Recorded And Given Its Forge Token By The Host

**Status:** Accepted (operator, 2026-10-30, with the project's one-click joining).
**Size:** M - two verbs of `porelo-host-person`, the sweep's timer and unit tests, with a VM run; measured M median 63
min, from three M builds (47, 63, 75).
**Blocked by:** [HO70](README.md#ho70); Porelo's task certificate check.

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** Every forge token a person or task uses on the host is made by the host, never travels between
persons, and goes with the person or task; every task's certificate is recorded on the host at its start.

- At admit, the sync makes the person's own forge user and no token, since Forgejo keeps only a token's hash. `sudo
  porelo-host-person forge-token` makes the one token, with `write:repository` and `write:issue`, and answers it once
  on stdout to the person's own call through the tunnel; their Porelo keeps it in their vault, and it lies in no file.
  A new call replaces the old token.
- At a task's start, `sudo porelo-host-person task <task>` takes the task's certificate on stdin, bounded in size, has
  Porelo check that the person's current key signed it for that task, and records it append-only in root's
  `/var/lib/porelo-host/tasks/<login>/`. The host's task gate then holds a token for the person's agent forge user, made
  for that task and used only for the task's repository, and passes the task's branch on with it; the task never sees
  it. `task --end <task>` deletes it; a daily sweep deletes every task token whose recorded certificate has expired.
- `porelo-host-person task --show <fingerprint>` answers a recorded certificate, read-only, to any admitted person, so a
  plain-key signature is traced to its certificate after the task key is destroyed.
- A host lock, the person's current key in the KRL, the removal of their last membership, or a purge deletes every
  token of the person's forge users, made by the host or not, and any password set on them.
- Goes: the `identities` stop and its `identities.tokens` files, the forge token kept in a file.

## Tests

- a certificate not signed by the person's key, or too long, is refused before anything is written; an expired task's
  token is gone after the sweep; a host lock leaves no token; the person's token is never in a file.
