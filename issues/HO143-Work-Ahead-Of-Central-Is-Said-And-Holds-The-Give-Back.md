# HO143 — Work Ahead Of Central Is Said And Holds The Give-Back

**Status:** Implementing.
**Kind:** Bug.
**Size:** S - `org status` adds each repository's central state, and `down` refuses while work is not at central,
with unit and Molecule checks.

**What must be true.** A person sees in `org status` which repository's `main` on the host is ahead of its central
forge, and the host is not given back while one is, unless the person gives it back anyway.

## Why

In a trial move `org status` said a repository was `taken` while the host's `main` held a merged commit no central
forge had. `taken` only says the repository was migrated, and nothing compared `main` with central there, so the
host could have been given back with the work on it. Every follow already writes that comparison for the members,
per project, under `/etc/porelo-host/organization/central/`.

## Plan

- **`org status`:** each repository row `taken` carries `central`, the follow's last answer for it in the same shape
  (`ahead` with its count of commits, `up-to-date`, `moved-on`, or `cannot-say` with why), matched by the name the
  repository goes by on the host's forge; no answer yet reads `cannot-say`. The window and the person's guide read it.
- **`down`:** before any person is purged or anything taken off, the play asks `porelo-host-project central-state`
  afresh for every project on the host and stops while a repository is `ahead` or `moved-on`, or `cannot-say` for a
  reason other than having no central forge, naming each with its state. The frontend's `--give-back-anyway`
  already gives the host back after a play that did not finish.
- **Red first:** a unit test of `org status` with a published central state `ahead`, and one of the play's refusal
  with a stand-in helper answering `ahead`, each red on today's code.

## Acceptance

- The unit tests, seen red on today's code and green after.
- A Molecule check: `down` on a host whose forge `main` holds a commit central lacks stops and names it.

