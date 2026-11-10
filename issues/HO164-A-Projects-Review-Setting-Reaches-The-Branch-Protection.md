# HO164 — A Project's Review Setting Reaches The Branch Protection

```json
{
  "$schema": "issue-1.json",
  "id": "HO164",
  "title": "A Project's Review Setting Reaches The Branch Protection",
  "state": "Backlog",
  "size": "XS",
  "priority": "Medium",
  "rank": 5,
  "blockedBy": [],
  "covers": "A project's `review: optional` or `required` reaches the host forge's protection of `main` on the next follow pass, so a single admin can merge."
}
```

**Why this size.** the finding did not reproduce; what is left is reading the move's log for its real cause.

**What must be true.** When a project's file says a repository's review is `optional`, the next follow pass sets the
host forge's protection of `main` to need no approval, and back to one when it says `required`; a project with one
admin can merge its own task's pull request without changing the forge by hand.

## Plan

- Read the log of the move whose admin met this, for the follow pass after the review change and the forge's answer.
  The operator holds that log; until the operator gives it, this issue waits on the operator.
- If the log shows the follow set the protection, or nothing of it, this issue is proposed Rejected to the operator.
  If it shows another cause, that cause is filed and this issue is Rejected in its favour.

## Acceptance

- A follow pass after the review entry changes makes the protection of `main` require exactly the approvals the file
  names, read from the forge's own answer.
- A protection changed by hand on the forge is set back to the file's value on the next pass.

## Measured

On the foo-org host (main at 888d1f0), 2026-11-09, both criteria held, so the finding did not reproduce there: with
foo-2's `review` set to `required` in foo-project's file (22:13Z), the follow pass of 22:15Z set main's protection
to one approval; set back to `optional` (22:29Z), the pass of 22:30Z set it to none; a protection of foo-1 set by
hand to two approvals was put back to none by that same pass. Each read from the forge's own answer. What the move's
admin met may have been another cause; the move's log should be read for it before anything is built.
