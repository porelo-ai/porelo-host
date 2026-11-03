# HO113 — A Renamed Branch Rule The Follow Does Not See

**Status:** Backlog.
**Size:** S - the follow's lookup of a repository's branch rule.

**What must be true.** A repository on the host's forge holds to the signed review and merge values, whatever a rule on
`main` is called. The follow asks only for a rule named exactly `main`. Forgejo matches plain names without regard to case
and prefers the older rule, so a Project Admin who renames it to `MAIN` keeps its values in force, and the follow adds a
new rule that has no effect.

## Acceptance

- A rule named `MAIN` with other values is brought to the signed values, and no second rule remains.
