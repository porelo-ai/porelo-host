# HO166 — A Room Refused While The Homeserver Is Away Is Asked Again

**Status:** Idea.

**What must be true.** A project's room that the gate refused because the homeserver did not answer is asked for again
on a later follow pass, and `up` fails when the homeserver it started does not answer. Today the follow records any
refusal of the gate (exit 78) as `room_refused` for good and never asks again, so a project made while the homeserver
was down has no conversation until the record is changed by hand; and `up` passes while the homeserver's unit keeps
failing.

## Acceptance

- A project followed while the homeserver is stopped gets its room on the first follow pass after it answers again.
- A refusal the gate means for good still stays recorded and is not asked again.
- `up` with a homeserver that exits at start fails at the homeserver's step, naming its unit.
