# HO146 — A Lent Forge Token Leaves The Person's Token

**Status:** Review.
**Size:** S - one verb's option in `porelo-host-person`, its sudoers line and its unit tests; Porelo's switch is its own.

**What must be true.** A task's builds keep reading the host's forge while Porelo starts tasks, refreshes a gate's
mirror and forwards a push: the person's `<forge>.person` token in their Porelo-Vault stays valid until the person's
own `porelo-host-forge-token`, push or pull replaces it, and two of Porelo's git commands at once never take each
other's token away.

## Why

`porelo-host-person forge-token` deletes every token of the caller's forge login and makes one new one. Porelo asks
for that for each git command of a gate against the host's forge and for taking the project at a task start, while
a task's builds watch reads the token the vault holds. So each start, mirror refresh and forwarded push deleted the
token in the vault, and the builds watch was answered `401` by Forgejo until the person ran
`porelo-host-forge-token` again.

## Plan

- `porelo-host-person`: `forge-token --lend` beside `forge-token` in the verb parsing; `person_forge_token` reads the
  login's token list and deletes, without `--lend`, every token but lends younger than a day, and with it only lends
  whose name carries a time 24 hours or more before now (`self.now`), then makes the one token. A lend's name is
  `porelo-host-lend-<UTC time>-<uuid>`, since Forgejo's API answers no token's creation time.
- `porelo-host-person.sudoers`: `forge-token --lend` beside `forge-token ""`.
- The header, `roles/porelo/README.md`, `doc/task-certificates.md` and `doc/local-forge.md` say it; a changelog entry.
- **Red first** in `tests/unit/roles/test_porelo_host_person_tasks.py`: a lend leaves the person token; a second lend
  leaves the first; a lend 24 hours old is deleted by the next lend; `forge-token` leaves a lend; lock deletes both.

## The shape

- `forge-token`, as today, deletes and makes only the login's person token, the one `porelo-host-forge-token` and
  `porelo-host-push` write into `<forge>.person`; of the lends it deletes only those a day old.
- `forge-token --lend` makes a token named `porelo-host-lend-<UTC time>-<uuid>` for one command and answers it alone on stdout,
  as today's verb does. It deletes only the login's lent tokens made more than 24 hours before, never the person
  token, so a long first clone of a mirror keeps its token.
- Revocation, lock, the last membership's removal and purge still delete every token of the login, and the daily
  sweep stays as it is: a lend a day old is deleted by the person's next `forge-token` or lend, and until then reaches
  no more than the person's own lasting token, of the same login and scopes, and lies in no file, so the sweep, which
  opens the forge only for an ended task, does not reach for lends. The scopes stay as they are. The sudoers drop-in admits `forge-token --lend` beside
  `forge-token`.
- Porelo uses `--lend` for its gate's git commands and for taking a project at a task start, and only on a host whose
  porelo-host has it: a sudo refusal there leaves a gate without the forge token and refuses a task start.

## Acceptance

- Unit tests, seen red on today's code: a lend leaves the person token valid; a second lend leaves the first; a lend
  older than 24 hours is deleted by the next lend and by the next `forge-token`; `forge-token` leaves a younger lend;
  a lock deletes both kinds; sudoers admits `forge-token` with no argument or `--lend` alone.
- On the next move's host, a task started after `porelo-host-forge-token` reads its builds without a `401`, also
  after a forwarded push.

