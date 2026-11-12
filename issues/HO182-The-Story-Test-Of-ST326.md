# HO182 — The Story Test Of ST326

```json
{
  "$schema": "issue-1.json",
  "id": "HO182",
  "title": "The Story Test Of ST326",
  "state": "Review",
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

## As built

`build/rehearse-steps/story-st326` plays ST326 as the test person on the rented rehearsal's host. It installs nothing:
the .deb or .rpm of porelo-agent-agy, porelo-agent-codex, porelo-message-transport-matrix, porelo-frontend and porelo
are fetched as the person from the repository the host installs from (`apt-get download` or `dnf download`) and
unpacked into a scratch directory. In each, THIRD-PARTY-NOTICES is held to the bill the package ships beside it: every
library the bill names that is not Porelo's own is named in the notices, the standard text of each license the bill
gives it stands there (LGPL's and Bouncy Castle's among them), and a package without a bill must still carry license
texts. The IntelliJ plugin's zip is fetched as an IDE fetches it, through `updatePlugins.xml` (`PORELO_STORY_PLUGINS`,
default the snapshots channel's), and bundles Porelo's own jars alone or names the others in a THIRD-PARTY-NOTICES.
Every issue of the story but porelo's B606 is in Review, so the expected line is `ST326 waiting on porelo#B606`; a
missing or short notice in the other packages is a failure. Not yet run: its run goes with the next rented
rehearsal, asked of the coordinator first.
