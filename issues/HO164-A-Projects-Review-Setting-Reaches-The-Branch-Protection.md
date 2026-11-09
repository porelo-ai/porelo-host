# HO164 — A Project's Review Setting Reaches The Branch Protection

**Status:** Backlog.

**What must be true.** When a project's file says a repository's review is `optional`, the next follow pass sets the
host forge's protection of `main` to need no approval, and back to one when it says `required`; a project with one
admin can merge its own task's pull request without changing the forge by hand.

## Acceptance

- A follow pass after the review entry changes makes the protection of `main` require exactly the approvals the file
  names, read from the forge's own answer.
- A protection changed by hand on the forge is set back to the file's value on the next pass.
