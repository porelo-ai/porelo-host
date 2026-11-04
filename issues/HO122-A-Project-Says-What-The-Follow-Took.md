# HO122 — A Project Says What The Follow Took

**Status:** Review.

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

## What was built

`org status` has `repositories` under each project, and a row with no `central` is a `why`. The field is new; a reader that does not know it is not
hurt.

**The missing line.** A unit test with the follow's real code takes an `optional` row whose repository the forge lists, with the one approval its
migration gave: the rule changes and the line comes, once, and the next follow says nothing. So a listed repository whose rule differs does not pass
unsaid. The migration is stubbed there. `foo-1` printed no line, so its rule was already right, or another run changed it, the timer's follow, whose
output reaches the journal and not the `org refresh` that was read, or the forge did not list it at that moment, in which case the follow says nothing
and sets nothing. That host is gone, and which it was is not shown. Molecule shows the list on a real forge, and a rented run can read the rule itself.
