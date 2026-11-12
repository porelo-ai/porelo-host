# HO165 — The Push To Central Takes Repository Names And Says A Refused Token

```json
{
  "$schema": "issue-1.json",
  "id": "HO165",
  "title": "The Push To Central Takes Repository Names And Says A Refused Token",
  "state": "Backlog",
  "size": "XS",
  "priority": "Medium",
  "rank": 6,
  "blockedBy": [],
  "covers": "`porelo-host-push` takes the project's repository names as well as the forge's, and says plainly when the central forge refuses the token."
}
```

**Why this size.** the push moved to porelo's `porelo host push` with the host's own program; what is left here is
measuring it on a host. Building it, where it still lacks, is Agent Core's in porelo.

**What must be true.** `porelo-host-push` takes a repository by the name the project's file gives it as well as by its
name on the host's forge, and when the central forge refuses the token it says that plainly, with the forge's answer,
instead of git's "could not read Username".

## Plan

- **What is there**, per Agent Core on porelo main (2026-11-10): `porelo host push <project> [<name>...]` takes a
  repository by the project's own name for it or by its central name, case-insensitively; an unknown name exits 64
  listing the pairs, a shared one exits 64 as ambiguous. A 401, at the preflight or from git, ends with
  `<name>: central forge <host[:port]> refused authentication (HTTP 401)`, exit 1; a 403 is not read as a refused
  token.
- **Measure** on the rehearsal's rented run: one push with a token the central forge refuses, and one push by each
  name; the answers go into this issue's record.
- What the measurement finds lacking is filed in porelo for Agent Core.

## Acceptance

- The same push given the project's repository name and the forge's name pushes the same repository.
- A token the central forge answers 401 to ends the push with a refusal naming the forge and the 401, and with nothing
  pushed; no prompt is tried.

## Measured

On the foo-org host (main at 888d1f0), 2026-11-09, as the test identity: `porelo-host-push foo-project foo-1` with a
token GitHub does not take ends "foo-1: the push failed; not pushed: none. Git said: fatal: could not read Username for
'https://github.com': terminal prompts disabled", exit 1; the same for `foo-project`. Nothing names the 401. The names
part could not be shown there: foo-project's file names its repositories as the forge does. The collection's move to the
host's own program removes `porelo-host-push`, so both parts go to the host program that takes over the gathered push.
