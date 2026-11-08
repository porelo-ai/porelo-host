# HO146 — A Lent Forge Token Leaves The Person's Token

**Status:** Idea.

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

## The shape

- `forge-token`, as today, deletes and makes only the login's person token, the one `porelo-host-forge-token` and
  `porelo-host-push` write into `<forge>.person`; it deletes no lent token.
- `forge-token --lend` makes a token named `porelo-host-lend-<uuid>` for one command and answers it alone on stdout,
  as today's verb does. It deletes only the login's lent tokens made more than 24 hours before, never the person
  token, so a long first clone of a mirror keeps its token.
- Revocation, lock, the last membership's removal and purge still delete every token of the login, and the daily
  sweep stays as it is. The scopes stay as they are. The sudoers drop-in admits `forge-token --lend` beside
  `forge-token`.
- Porelo uses `--lend` for its gate's git commands and for taking a project at a task start, and only on a host whose
  porelo-host has it: a sudo refusal there leaves a gate without the forge token and refuses a task start.

## Acceptance

- Unit tests, seen red on today's code: a lend leaves the person token valid; a second lend leaves the first; a lend
  older than 24 hours is deleted by the next lend; `forge-token` leaves a lent token; revocation deletes both kinds.
- On the next move's host, a task started after `porelo-host-forge-token` reads its builds without a `401`, also
  after a forwarded push.

## Open questions

- Whether this contract is built for the next move.
