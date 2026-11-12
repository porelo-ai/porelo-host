# HO180 — The Story Test Of ST41

```json
{
  "$schema": "issue-1.json",
  "id": "HO180",
  "title": "The Story Test Of ST41",
  "state": "Backlog",
  "size": "M",
  "priority": "High",
  "rank": 4,
  "blockedBy": [],
  "covers": "A script beside the rehearsal scripts plays ST41 on the test VM: in a sample Maven repository `porelo project init` writes the `.porelo.yml` and `project.yml` drafts, each proposed value names its source, and after a change in the local repository `refresh` reads the project again and shows it; it reports passed, failed with the step, or waiting on porelo-project's PJ52."
}
```

**Why this size.** a sample Maven repository made by the script, the drafts' values and sources checked one by one, and a refresh round trip.

**What must be true.** The script plays ST41 ("`porelo project init` proposes tools and rules", porelo-project) once on the test VM as a person would, step by
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
