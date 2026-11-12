# HO184 — The Story Test Of ST40

```json
{
  "$schema": "issue-1.json",
  "id": "HO184",
  "title": "The Story Test Of ST40",
  "state": "Backlog",
  "size": "L",
  "priority": "High",
  "rank": 8,
  "blockedBy": [],
  "covers": "A script plays ST40 on the rented KVM host of 2026-11-13 with the forge and the pool: porelo's and the four agent adapters' acceptance legs each take a pool account by kind and their Builds are green, the same workflows rent a server on GitHub, and no workflow names a provider; it reports passed, failed with the step, or waiting on porelo's B322 or CC40, PI40, OM37 and AG05."
}
```

**Why this size.** five repositories' legs on the host's forge, their twins on GitHub, and the rental's own set-up ([HO178](README.md#ho178)); it runs on the rental, not on the test VM.

**What must be true.** The script plays ST40 ("Legs on pool machines, the same workflow on both forges", porelo-project) once on the test VM as a person would, step by
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
