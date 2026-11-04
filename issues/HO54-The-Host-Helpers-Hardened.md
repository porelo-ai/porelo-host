# HO54 — The Host's Helpers Hardened

**Status:** Idea.

**What must be true.** The points a read-only review of sprint 6j's stack found and the sprint left for later, to be
planned with the findings of the operator's 6j test:

- The SSH drop-in for the people is read before any other drop-in that could set the keys' source for them, and says
  no password and no keys command for the group.
- `porelo-host-project add` finds and removes an organization or publisher the forge made although its answer was
  lost to a timeout, so a retry is not refused for a name it took itself.

Two points of that review have no subject today: `porelo-host-stop --stdin` refuses `forge-certificate`, as the forge has
no certificate, and `porelo-host-forge-password` no longer exists, as the forge has no password.
