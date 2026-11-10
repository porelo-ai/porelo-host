# HO141 — The Move Check Reads Push And Pull Request From The Forge

```json
{
  "$schema": "issue-1.json",
  "id": "HO141",
  "title": "The Move Check Reads Push And Pull Request From The Forge",
  "state": "Review",
  "size": "S",
  "priority": "Medium",
  "rank": 12,
  "blockedBy": [],
  "covers": "Bug: the move check reads the push and the pull request from the host's forge, and names the Build not configured without `builds:`."
}
```

**Why this size.** `build/move-check.sh` reads two lines anew, with their unit tests in `tests/unit/test_move_tools.py`.

**What must be true.** On a guarded project without a `builds:` block, the move check is green for a task whose push
reached the host's forge and whose pull request is open there, and it names the Build as not configured instead of
failing it. It is a bug.

## Why

In a trial move the task's work was on the host's forge with its pull request open, yet the check failed both lines.
It still took the pushed commit from the `build` line and the pull request from the `pull req` line of
`porelo task status`. Porelo prints both only from its builds record, which a project without `builds:` never has.
Porelo keeps no record of a forwarded push or its pull request: `porelo gate approve` prints them once, and
`gate pending` shows the commit only while the push waits.

## Plan

- **The push:** the head of the branch `porelo/<task>` on the host's forge, or the next free name the gate's approve
  takes, read with `git ls-remote` as the person, through the credential helper on the person's `<forge>.person`
  vault entry, never a token on a command line.
- **The pull request:** the open pull request with head `porelo/<task>` and base the repository's default branch,
  read from the forge's API with the same credential, given to `curl` on standard input.
- **The Build:** the build reader's exit 78, a project without `builds:`, reads "not configured" and does not fail the
  check; any other failure still fails it.
- **Red first:** stand-ins for `porelo`, `git` and `curl`: a guarded project whose push and pull request exist is red
  on today's script; a missing branch head and a missing pull request each fail and say which; no stand-in sees the
  token among its arguments.

## Acceptance

- The unit tests, seen red on today's script and green after.
- On the next move's host, the push and pull request lines green for a guarded task, the Build named not configured.
