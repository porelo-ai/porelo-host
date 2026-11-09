# HO153 — The Web Gate Keeps A Browser's Connection

**Status:** Backlog; stopped 2026-11-09 by the operator: waits on the porelo-host CLI.

**What must be true.** A page of the host's forge loads over a few connections of the person's browser that stay
open, not one new connection and one new gate process for every request. A page with many parts, or an Actions page
that polls, starts few processes. Each request on a kept connection is still checked as the first one is: the peer,
the site and the route.
