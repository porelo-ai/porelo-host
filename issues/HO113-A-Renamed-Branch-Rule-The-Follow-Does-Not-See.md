# HO113 — A Renamed Branch Rule The Follow Does Not See

```json
{
  "$schema": "issue-1.json",
  "id": "HO113",
  "title": "A Renamed Branch Rule The Follow Does Not See",
  "state": "Review",
  "size": "S",
  "priority": "Medium",
  "rank": 32,
  "blockedBy": [],
  "covers": "The follow holds a branch rule to the signed values whatever the rule on `main` is called"
}
```

**Why this size.** the follow's lookup of a repository's branch rule.

**What must be true.** A repository on the host's forge holds to the signed review and merge values, whatever a rule on
`main` is called. The follow asks only for a rule named exactly `main`. Forgejo matches plain names without regard to case
and prefers the older rule, so a Project Admin who renames it to `MAIN` keeps its values in force, and the follow adds a
new rule that has no effect.

## Acceptance

- A rule named `MAIN` with other values is brought to the signed values, and no second rule remains.

## What is built

The follow reads a repository's rules and holds whichever rule on `main` is in force, the oldest of those differing only
in case, under its own name. It sets that one first, then deletes the others, so `main` stands protected throughout. Only
differences of case count: a pattern such as `ma*` is not looked at here.
