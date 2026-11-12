# HO182 — The Story Test Of ST326

```json
{
  "$schema": "issue-1.json",
  "id": "HO182",
  "title": "The Story Test Of ST326",
  "state": "Backlog",
  "size": "M",
  "priority": "High",
  "rank": 6,
  "blockedBy": [],
  "covers": "A script beside the rehearsal scripts plays ST326 on the test VM: it installs or unpacks the .deb and .rpm of porelo-agy, porelo-codex, porelo-message-matrix and the window and the IntelliJ plugin's zip, finds THIRD-PARTY-NOTICES in each naming every compiled-in library with its full license text, LGPL-3.0 and Bouncy Castle among them, against each build's dependency list; it reports passed, failed with the step, or waiting on porelo's B606."
}
```

**Why this size.** five packages fetched and opened, each notice file compared with a dependency list; an .rpm is unpacked where the VM cannot install it.

**What must be true.** The script plays ST326 ("Every package carries the notices of what it compiles in", porelo-project) once on the test VM as a person would, step by
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
