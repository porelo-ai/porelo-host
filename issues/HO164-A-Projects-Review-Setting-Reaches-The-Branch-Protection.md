# HO164 — A Project's Review Setting Reaches The Branch Protection

**Status:** Backlog.

**What must be true.** When a project's file says a repository's review is `optional`, the next follow pass sets the
host forge's protection of `main` to need no approval, and back to one when it says `required`; a project with one
admin can merge its own task's pull request without changing the forge by hand.

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
