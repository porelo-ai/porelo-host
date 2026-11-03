# HO108 — Approved Commits Not Yet At The Central Forge

**Status:** Review.
**Size:** M - a verb of the project helper, a published file per project, one line of the push tool, their tests and a
contract the interface reads.

**What must be true.** A project's person, or the interface on their behalf, can ask the host without root and without a
central token how each repository's approved `main` stands against the central forge, and gets one of four answers: how
many approved commits the central forge lacks; up to date; the central forge moved on or the two went apart, so a push
would be refused; or cannot say, as no read key is held for that repository or the forge is out of reach, which never
reads as up to date. The answer says how old it is, and it is only ever a prompt: the push itself still decides.

## Plan

- `porelo-host-project central-state <project>`, root's: for each repository of the project on the host's forge, asks
  the central forge's `main` by `git ls-remote` with that repository's read key and the pinned host keys, so nothing is
  cloned at each follow and no token is left on the forge by asking its API, and compares it inside the forge's container with the local `main`: the same commit is up to
  date; a central commit the local `main` descends from is `ahead` by the count between them; a commit not known there,
  or not an ancestor, is `moved-on`. It changes nothing and writes neither forge. A failure of one repository is that
  repository's `cannot-say` with its reason.
- The follow runs it for each migrated project, after access is applied, and writes
  `/etc/porelo-host/organization/central/<project>.json` with the time it read, readable by the project's unlocked
  members by the same ACL as the project's file. A helper that fails leaves an answer with no repositories, which reads
  as cannot say; it never fails the follow.
- `porelo-host-push --central <project>`, in the person's own account, prints that file. No token and no root. With no
  file it can read, it refuses with 69.
- Red first: each of the four answers against real Git repositories; the follow's file and ACL for members alone; a
  failing helper not failing the follow; a person with no file refused.

## Acceptance

- Each answer is seen against real repositories, and cannot say never reads as up to date.
- A person who is no member cannot read a project's answer.
- The follow's run stays bounded while the central forge cannot be reached.
