# HO181 — The Story Test Of ST320

```json
{
  "$schema": "issue-1.json",
  "id": "HO181",
  "title": "The Story Test Of ST320",
  "state": "Review",
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

## As built

`build/rehearse-steps/story-st320` plays ST320 as the test person on the rented rehearsal's host, as a developer of
the repositories would: fresh shallow checkouts of porelo-buildtools, porelo-planner and porelo from
`PORELO_STORY_FORGE` (default `https://github.com/porelo-ai`). The planner's executable must be on the person's PATH
and name `check-commits`, `check-citations` and `stage`; porelo must build `porelo-ffm-check` and `porelo-cpu-check`
itself; porelo-buildtools must hold neither those modules, nor a `plan` command, nor the `stories` module, the
`stories`, `issues`, `stage`, `check-commits` and `check-pushes` commands or `stats/`. BT70 and BT72 are in Review and
their checks pass on today's main; BT71 waits for the planner's pinned executable, so the expected line is `ST320
waiting on porelo#B630, porelo-buildtools#BT71` or less. The planner's download and the commands it runs are filled in on
the first run after BT71 publishes it, as the story-test rules allow. Not yet run: its run goes with the next rented
rehearsal, asked of the coordinator first; a clone the host cannot make is the first thing that run shows.
