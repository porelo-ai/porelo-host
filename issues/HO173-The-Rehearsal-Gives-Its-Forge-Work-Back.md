# HO173 — The Rehearsal Gives Its Forge Work Back

```json
{
  "$schema": "issue-1.json",
  "id": "HO173",
  "title": "The Rehearsal Gives Its Forge Work Back",
  "state": "Idea",
  "size": "-",
  "priority": "Low",
  "rank": 99,
  "blockedBy": [],
  "covers": "build/rehearse-move.sh's down step brings the host forge's work to central, or gives the host back anyway by its explicit way, so a rehearsal whose forge moved on still runs down."
}
```

**What must be true.** A rehearsal whose host forge holds work that central does not have still runs its `down` step
to its end:

- Either a step brings that work to central first, or the `down` step takes the explicit "give it back anyway" way and
  says so in its line.
- The host's guard stays as it is. `down` without that way still refuses with "work on this host's forge is not at
  central".

**Why.** On 2026-11-11 the joint round's host 192.168.122.108 refused its `down`: foo-project/foo-1 had moved on from
central on the host's forge, through a merge of a workflow branch and the gates' pull requests. The guard was right.
The rehearsal had no way past it, and the host's software stayed until its server was deleted.
