# HO104 — A Refusal's Why Lasts

**Status:** Idea.

**What must be true.** A refused migration's `why` in `org status` stands until a later try ends otherwise. Today the next
five-minute follow, which has no token, sets `why` back to null, so a refusal's reason is gone within minutes while the
state stays `waiting-for-token`. The same holds for what [HO100](README.md#ho100) brings.

**Plan.** The follow keeps a refusal's `why` when it makes no try of its own, and replaces it only when a later try ends.
A test holds it.
