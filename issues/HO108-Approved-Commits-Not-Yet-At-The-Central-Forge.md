# HO108 — Approved Commits Not Yet At The Central Forge

**Status:** Idea.

**What must be true.** A project's person, or the interface on their behalf, can ask the host without root and without a
central token how each repository's approved `main` stands against the central forge, and gets one of four answers: how
many approved commits the central forge lacks; up to date; the central forge moved on or the two went apart, so a push
would be refused; or cannot say, as no read key is held for that repository or the forge is out of reach, which never
reads as up to date. The answer says how old it is, and it is only ever a prompt: the push itself still decides.

## To be checked

- The host holds a read-only key per migrated repository, and `check_read_keys` in `porelo-host-project` compares a
  project's local refs with the central forge with it, for every ref and under root. Whether the five-minute follow can
  keep this for `main` alone, in what record, and through which person-facing line it is read, as `org status` is root's.
- The cost of asking the central forge each follow, as the comparison today clones each repository's mirror.
