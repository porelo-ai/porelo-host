# HO195 — The Host's Markdown Issues Go At The Cut-Over

```json
{
  "$schema": "issue-1.json",
  "id": "HO195",
  "title": "The Host's Markdown Issues Go At The Cut-Over",
  "state": "Accepted",
  "size": "S",
  "priority": "High",
  "rank": 1,
  "blockedBy": [],
  "covers": "Once the host's issues are carried over to GitHub Issues on the cut-over day, `issues/` and the shared-rules step that checks it are removed, and the story rehearsal that plays the issue check is retired; until then nothing changes."
}
```

**Why this size.** Deleting `issues/` and one workflow step, plus one rehearsal script and the rules and documents that
point at `issues/`. No program or role changes: S.

**What must be true.** Projects move from Markdown issues to GitHub Issues on one cut-over day. Until that day,
porelo-host's `issues/` and its checks stay as they are. After it, the repository holds no Markdown issue, and no step of
its Build, prepush or rehearsal scripts reads one.

## Plan

- Done only after the carry-over has written every open issue of `issues/` to GitHub Issues, each with its old id.
- Delete `issues/`: the issue files, `README.md` and the shared `workflow.yml` copy.
- `.github/workflows/shared-rules.yml`: drop the step "The issue heads" (`issues check issues`). Keep "No citation of
  an issue that goes stale" (`check-citations .`) as long as the shared tools keep that command, now without
  `issues/`.
- `build/rehearse-steps/story-st346` plays a story test of the Markdown issue check. Retire it with its line in the
  rehearsal's step list, and with its unit test if one names it.
- `AGENTS.md`'s own part and `.agents/skills/host-build`: drop what points at `issues/`. The shared block and the
  shared skills follow the shared change, never one copy.
- Red first: a test that `story-st346` is no longer in the rehearsal's step list fails today.

## Acceptance

- The Build and shared-rules workflows pass on a commit without `issues/`. `check-citations .` passes there.
- `git grep -n 'issues/'` finds nothing but the changelog's history, and that search is shown to find a known hit
  before the removal.
- Before the cut-over: nothing of this is merged.

## To be checked

- Whether the shared tools' `check-citations` still runs after the cut-over, or goes too. That decides whether its step
  stays.
- Whether the carry-over also takes the Finished and Rejected rows of the index, or whether they are dropped. They
  live only in `issues/README.md`.
