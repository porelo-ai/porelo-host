# HO180 — The Story Test Of ST41

```json
{
  "$schema": "issue-1.json",
  "id": "HO180",
  "title": "The Story Test Of ST41",
  "state": "Review",
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

## As built

`build/rehearse-steps/story-st41` plays ST41 as the test person on the rented rehearsal's host: a sample Maven module
whose Java release only its parent sets, the parent named by coordinates, committed in a scratch checkout. `porelo
project init --json` must recognize it, give a `project.yml` draft, and name a source (a file, or a note for a value
with none) for every value it proposes; while the parent is missing from the person's local Maven repository the
release must be unknown and name the parent; with the parent placed there, as building it once would, the same command
must name release 21; the checkout stays without a changed or new file. The answer holds no `.porelo.yml` draft for
the tools yet, which PJ52 (porelo-project) asks for, so the expected line is `ST41 waiting on porelo-project#PJ52`.
The checkout and the placed parent are removed at the end; a parent of the same coordinates already there stops the
run before anything is written. Not yet run: its run goes with the next rented rehearsal, asked of the coordinator
first.
