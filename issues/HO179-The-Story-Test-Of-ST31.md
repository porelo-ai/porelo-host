# HO179 — The Story Test Of ST31

```json
{
  "$schema": "issue-1.json",
  "id": "HO179",
  "title": "The Story Test Of ST31",
  "state": "Review",
  "size": "S",
  "priority": "High",
  "rank": 3,
  "blockedBy": [],
  "covers": "A script beside the rehearsal scripts plays ST31 on the test VM as a person at the command line: it pastes a long key with odd characters at `vault put`'s prompt through a terminal, reads it back whole, starts an agent with a provider Porelo does not know and sees it refused by name before anything starts; it reports passed, failed with the step, or waiting on porelo's B228, P09 or B316."
}
```

**Why this size.** a terminal-driven script of two short scenarios on a host after `up`; the pasted prompt needs a pseudo-terminal.

**What must be true.** The script plays ST31 ("Keys and providers without stumbling", porelo-project) once on the test VM as a person would, step by
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

`build/rehearse-steps/story-st31` plays ST31 as the test person on the rented rehearsal's host: an Ed25519 key with a
comment of quotes, umlauts and shell characters, made there by `ssh-keygen`, is stored once with `--from-file` and once
pasted at `vault put`'s prompt through a pseudo-terminal, and `vault list` must name both with the same type and
length; neither put may warn that no provider is declared; a provider file `example-unknown` declaring `openai`, its
credential stored, is chosen for Pi with `--provider`, and the start must be refused naming it, with no task left.
It ends `ST31 passed`, `ST31 waiting on porelo#B228, ...` (77) or `ST31 failed at <step>: ...`, and cleans up the
entries, the file and any task. `rehearse-move.sh` runs every `story-*` step before `tasks`; a story's outcome goes to
`<report>/stories` and the steps as `STORY`, and never ends the rehearsal. All three porelo issues are in Backlog, so
the expected line is `ST31 waiting on porelo#B228, porelo#B316, porelo#P09`. Not yet run: its run goes with the next
rented rehearsal, asked of the coordinator first.
