# HO137 — A Task's Account Opens Its Pull Request

```json
{
  "$schema": "issue-1.json",
  "id": "HO137",
  "title": "A Task's Account Opens Its Pull Request",
  "state": "Review",
  "size": "S",
  "priority": "Medium",
  "rank": 17,
  "blockedBy": [],
  "covers": "The task's token opens its pull request `porelo/<task>` → `main` on the host's forge, and the person's approval counts, measured in the follow act."
}
```

**Why this size.** mostly a measurement in the Molecule scenario's follow act; a host change only where it fails.

**What must be true.** On the host's forge, the token a task start makes for the person's task account
`porelo-<login>` opens a pull request from `porelo/<task>` to `main`. The person `<login>` may approve it, and that
approval counts for `main`'s protection, so a project with one member merges its tasks' work with `review:
"required"`. The host keeps no lasting token for it: Porelo holds the task's token in its gate and opens the pull
request with it, after its approve has forwarded the work to `porelo/<task>`. That is porelo's part; the window shows
the pull request.

## Why

On the rehearsal's host (operator, 2026-11-06), PR #1 of `porelo/porelo-message-sluice`, opened by the person, could
not be approved by its author in Forgejo 17.0.0, and the host's rule wants one approval from `Owners` or `developers`.
The task's own account as the pull request's author keeps that rule meaningful at any number of members.

## Plan

- **Already there:** each person's tasks push as `porelo-<login>`, a member of the project's `developers` team, and
  each task start makes a token of that account for that task alone (`write:repository,read:package`), answered on
  stdout into the gate and deleted by `task --end`.
- **Measured in the follow act, red first where it fails:** with a task's token, open a pull request
  `porelo/<task>` → `main`; approve it as the person; merge it by fast-forward as the person; and a second person
  outside `Owners` and `developers` cannot approve it in a way that counts.
- **Changed only if a measurement fails:** the token's scopes in `porelo-host-person`, the `developers` team's units,
  or the protection's approval whitelist, each with its unit test.
- **Documented:** doc/local-forge.md, "The person's two decisions", says who opens the pull request.

## Acceptance

- The follow act opens, approves and merges a task's pull request as above, green on the Molecule scenario.
- The decision's text in doc/local-forge.md names the task's account as the pull request's author.

## To be checked

- Settled with porelo's part: the account is the person's task account, one per person and project, with a token
  per task, not a new account per task or per repository's agent.

## Done

- **Measured, no host change needed:** the follow act starts a task `prown` of `fb`, pushes `porelo/prown` with the
  task's token, and opens the pull request to `main` with that token; its author is `porelo-fb`. Unapproved, `fb`'s
  merge is refused. An account outside `Owners` and `developers`, a writer of the repository, approves; Forgejo takes
  the review and the merge is still refused. `fb` approves, and the fast-forward merge as `fb` succeeds. Green on the
  Molecule scenario (2026-11-06, 197 facts of the follow).
- The outsider is made by Forgejo's own `admin user create --random-password`, so no password is on a command line,
  and is purged with the task's end.
- doc/local-forge.md, "The person's two decisions", names the task's account as the pull request's author.
