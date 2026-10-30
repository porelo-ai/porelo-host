# HO71 — A Task Recorded And Given Its Forge Token By The Host

**Status:** Accepted (operator, 2026-10-30, with the project's one-click joining).
**Size:** M - two verbs of `porelo-host-person`, the sweep's timer and unit tests, with a VM run; measured M median 63
min, from three M builds (47, 63, 75).
**Blocked by:** [HO70](README.md#ho70); Porelo's task certificate check.

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** Every forge token a person or task uses on the host is made by the host, never travels between
persons, and goes with the person or task; every task's certificate is recorded on the host at its start.

- At admit, the sync makes one token for the person's own forge user, with `write:repository` and `write:issue`, written
  as root into `~<login>/.config/porelo-forge/token`, 0600, the person's; their Porelo reads it over SSH for Git over
  HTTP.
- At a task's start, `sudo porelo-host-person task <task>` takes the task's certificate on stdin, bounded in size, has
  Porelo check that the person's current key signed it for that task, records it append-only in root's
  `/var/lib/porelo-host/tasks/<login>/`, and makes a token for the person's agent forge user with the same scopes,
  answered on stdout only. `task --end <task>` deletes the token; a daily sweep deletes every task token whose recorded
  certificate has expired.
- `porelo-host-person task --show <fingerprint>` answers a recorded certificate, read-only, to any admitted person, so a
  plain-key signature is traced to its certificate after the task key is destroyed.
- A lock, removal or purge deletes the person's and their tasks' tokens.
- Goes: the `identities` stop and its `identities.tokens` files, the forge token kept in the person's vault.

## Tests

- a certificate not signed by the person's key, or too long, is refused before anything is written; an expired task's
  token is gone after the sweep; a lock leaves no token.
