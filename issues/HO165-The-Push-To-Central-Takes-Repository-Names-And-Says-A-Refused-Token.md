# HO165 — The Push To Central Takes Repository Names And Says A Refused Token

**Status:** Backlog.

**What must be true.** `porelo-host-push` takes a repository by the name the project's file gives it as well as by its
name on the host's forge, and when the central forge refuses the token it says that plainly, with the forge's answer,
instead of git's "could not read Username".

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
