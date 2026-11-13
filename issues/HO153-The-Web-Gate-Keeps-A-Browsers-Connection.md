# HO153 — The Web Gate Keeps A Browser's Connection

```json
{
  "$schema": "issue-1.json",
  "id": "HO153",
  "title": "The Web Gate Keeps A Browser's Connection",
  "state": "Backlog",
  "size": "-",
  "priority": "Low",
  "rank": 2,
  "blockedBy": [],
  "covers": "Stopped by the operator, waits on the porelo-host CLI: the forge's web gate keeps a browser's connection open for several requests, each checked as the first, so a page starts few gate processes."
}
```

**2026-11-09:** Stopped by the operator: waits on the porelo-host CLI.

**What must be true.** A page of the host's forge loads over a few connections of the person's browser that stay
open, not one new connection and one new gate process for every request. A page with many parts, or an Actions page
that polls, starts few processes. Each request on a kept connection is still checked as the first one is: the peer,
the site and the route.
