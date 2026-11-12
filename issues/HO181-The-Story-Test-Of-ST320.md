# HO181 — The Story Test Of ST320

```json
{
  "$schema": "issue-1.json",
  "id": "HO181",
  "title": "The Story Test Of ST320",
  "state": "Backlog",
  "size": "M",
  "priority": "High",
  "rank": 5,
  "blockedBy": [],
  "covers": "A script beside the rehearsal scripts plays ST320 on the test VM: in checkouts of the repositories it runs the shared rules from the planner's tools, writes a stage line and makes a board move by the planner's format, runs Core's native-image checks from porelo, and finds in porelo-buildtools no module or command nobody calls; it reports passed, failed with the step, or waiting on BT71, BT72 or porelo's B630."
}
```

**Why this size.** checkouts of several repositories on the VM and a check per moved tool; no machine of its own beyond the VM.

**What must be true.** The script plays ST320 ("The work tools live with their users", porelo-project) once on the test VM as a person would, step by
step, and its run ends with one line for the story: passed, failed naming the step, or waiting on the issue still
missing. It lives in `build/` beside the rehearsal scripts.

**Why.** Part of ST347 (porelo-project), "Every story played through once, as a user would", on the operator's order
of 2026-11-12.

## Rules for this story test (operator, 2026-11-12)

- A test script is test tooling, not production code: no tests for the test script, no red-first, no review loops (one
  Sonnet reading at most). The script is proven by its run on the VM.
- On the VM a failing script is fixed ad hoc on the spot and the run carries on; every fault found, in the script or in
  the product, is collected, not fixed one by one. After the run: product faults become estimated Backlog issues,
  script fixes go into one commit, then one new run.
- One VM run at a time on this host, through the coordinator: asked before it starts, posted when it ends. No second
  VM, no Molecule beside it; cleaned up after.
- A story whose issues are not all in Review yet still gets its script and one run; the run names the missing issue as
  an expected failure.
