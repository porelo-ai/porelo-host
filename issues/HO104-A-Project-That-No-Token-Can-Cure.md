# HO104 — A Project That No Token Can Cure

**Status:** Idea.

**What must be true.** A project with no usable central address has a state of its own in `org status`, as it does not
wait for a token and a token cannot cure it. Its `why` also lasts: today the next five-minute follow, which has no
token, sets `why` back to null, so a refusal's reason is gone within minutes while the state stays
`waiting-for-token`. The same holds for what [HO100](HO100-A-Project-Helpers-Own-Words-In-Status.md) brings.

**Plan.** The follow says `waiting-for-address` for such a project, token or none, and refresh's check of what waits for
a token leaves it out. A refused migration's `why` stands until a later try ends otherwise. The interface reads the new
state. A test holds both.
