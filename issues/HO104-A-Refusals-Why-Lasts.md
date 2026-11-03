# HO104 — A Refusal's Why Lasts

**Status:** Review.
**Size:** S - one state field in the follow and its tests, no contract other repositories read.

**What must be true.** A refused migration's `why` in `org status` stands until a later try ends otherwise. Today the next
five-minute follow, which has no token, sets `why` back to null, so a refusal's reason is gone within minutes while the
state stays `waiting-for-token`. The same holds for what [HO100](README.md#ho100) brings.

## Plan

- `follow_project_forge` in `porelo-host-person` keeps the refusal of a migration try in the project's progress record,
  drops it when a later try succeeds, and replaces it when a later try is refused. `follow_projects` shows it as `why`
  while the organization names nothing newer about the project.
- Red first in `test_porelo_host_person_follow.py`: a refused migration's `why` stands through a follow without a token,
  is replaced by a later refusal, and is gone after a later success.

## Acceptance

- The `why` stands across follows without a token and ends with the next try, seen failing with the record not kept.
