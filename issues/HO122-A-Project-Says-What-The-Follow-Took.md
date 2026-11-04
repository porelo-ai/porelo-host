# HO122 — A Project Says What The Follow Took

**Status:** Idea.

**What must be true.** `org status` says which of a project's repositories the host took and why any was not. A row the host can
give no task is named there, not found at the task's refusal.

## Why, from a run against real GitHub

`org refresh` answered `foo-project` `carried`, `why: null`, on a host whose repositories had been taken. Nothing said which; it
took a script reading root's `host-projects.json` and the read-key manifest to show it.

- **A row with no `central` is skipped with no word:** `follow_take_named_repositories` goes on, the project still reads `carried`
  and `why` stays empty. The first sign is the task's refusal. It was only avoided by mending the rows beforehand.
- **`taken` and `repositories_why` stand in root's record alone,** and `why` shows only what was refused.
- **One line was missing and stays unexplained.** The follow prints `main's review is ...` only when it changes a rule. `migrate`
  makes `main` with one approval, so an `optional` row must change it. `foo-2` and `foo-project` printed the line, `foo-1`, also
  `optional` with `central` and taken, did not. No read of its rule on the forge was reported before the host went back. So
  either a rule was already right on a first refresh, or something was missed.

## Plan

- `org status` gains, per project, each repository of the signed file with its state: taken, waiting and why, or no `central`.
- A row with no `central` on a host with a forge is a `why`, in words a person can act on.
- A unit test with the follow's real code for one `optional` row after a migration: that the rule changes and says so, which settles
  the line or finds what was missed.

## Acceptance

- `org status` for a project with rows taken, waiting and without `central` names each, in unit tests of the helper and in Molecule.
- `doc/local-forge.md` says how to read it.
- The missing line explained, or shown not to happen again.
