# HO165 — The Push To Central Takes Repository Names And Says A Refused Token

**Status:** Backlog.

**What must be true.** `porelo-host-push` takes a repository by the name the project's file gives it as well as by its
name on the host's forge, and when the central forge refuses the token it says that plainly, with the forge's answer,
instead of git's "could not read Username".

## Acceptance

- The same push given the project's repository name and the forge's name pushes the same repository.
- A token the central forge answers 401 to ends the push with a refusal naming the forge and the 401, and with nothing
  pushed; no prompt is tried.
