# HO195 — The Host's Markdown Issues Go At The Cut-Over

```json
{
  "$schema": "issue-1.json",
  "id": "HO195",
  "title": "The Host's Markdown Issues Go At The Cut-Over",
  "state": "Implementing",
  "size": "S",
  "priority": "High",
  "rank": 1,
  "blockedBy": [],
  "covers": "In the step after the host's issues are carried over to GitHub Issues and checked, porelo-host moves to the shared tools that recognize the tracker, and `issues/`, `stats/`, the shared-rules step that checks the issues and the story rehearsal that plays it are removed; until then nothing changes."
}
```

**Why this size.** Deleting `issues/`, `stats/` and one workflow step, one version in `build/pom.xml`, plus one
rehearsal script and the rules and documents that point at `issues/`. No program or role changes: S.

**What must be true.** Projects move from Markdown issues to GitHub Issues on one cut-over day, on which only the
project's `project.yml` changes: porelo-host's `issues/` and its checks stay as they are and keep passing. In the step
after the carry-over and its check, the repository drops its Markdown issues: it then holds none, and no step of its
Build, prepush or rehearsal scripts reads one.

## Plan

- Done only after the carry-over has run on the cut-over day: it writes every open issue of `issues/` to GitHub
  Issues, each with its old id, and reads every row of the index once for the highest number the prefix `HO` ever
  used, which it writes into `project.yml`'s `issue_floor`, so a new issue never takes a used number. Finished and Rejected rows are not carried over; they go with
  `issues/README.md`.
- Delete `issues/`: the issue files, `README.md` and the shared `workflow.yml` copy.
- `.github/workflows/shared-rules.yml`: drop the step "The issue heads" (`issues check issues`). Keep "No citation of
  an issue that goes stale" (`check-citations .`): the rule that code and shipped text never cite an issue number
  stays after the cut-over, for the old ids and the GitHub numbers alike, and the shared tools keep the command,
  reading no `issues/`.
- `build/rehearse-steps/story-st346` plays a story test of the Markdown issue check. Retire it, and its sentence in
  `doc/testing.md`. The rehearsal runs every `build/rehearse-steps/story-*` it finds, so no list names it and no unit
  test holds it; as a test script it gets none.
- Delete `stats/`: once the project's tracker is GitHub Issues the shared tools write and read no stage record.
- `build/pom.xml`: `porelo.buildtools.version` to `0.5.3-SNAPSHOT`, whose shared tools read the project's tracker.
  The `0.5.2-SNAPSHOT` in use stops check-commits unanswered when `issues/` holds no prefix and refuses a commit
  deleting a stage record, so this commit is pushed only once the snapshot recognizing the tracker is published.
- `build.yml` and `release.yml`'s `paths-ignore`, `build/ansible-lint.yml`, `build/yamllint.yml` and
  `build/yamllint-ansible.yml`: drop `issues/`. `CONTRIBUTING.md`: a change starts in porelo-project's planning or as
  an issue of this repository on GitHub.
- `AGENTS.md`'s own part and `.agents/skills/host-build`: drop what points at `issues/`. The shared block and the
  shared skills follow the shared change, never one copy.
- No program changes, so no unit test goes red first. Measured instead: on this tree with `issues/` and `stats/`
  deleted, `check-commits` from `0.5.2-SNAPSHOT` stops unanswered, and from the new snapshot, with porelo-project's
  `project.yml` naming the tracker, it passes.

## Acceptance

- The Build and shared-rules workflows pass on a commit without `issues/`. `check-citations .` passes there.
- `git grep -n 'issues/'` finds nothing but the changelog's history, and that search is shown to find a known hit
  before the removal.
- `check-citations .` still refuses an issue number, `HO12` or `porelo-ai/porelo-host#12`, written into code on that commit.
- Before the cut-over: nothing of this is merged.
