# HO107 — A Project That No Token Can Cure

```json
{
  "$schema": "issue-1.json",
  "id": "HO107",
  "title": "A Project That No Token Can Cure",
  "state": "Idea",
  "size": "-",
  "priority": "Medium",
  "rank": 17,
  "blockedBy": [],
  "covers": "A project with no usable central address has a state of its own, `waiting-for-address`, as no token can cure it"
}
```

**What must be true.** A project with no usable central address has a state of its own in `org status`, as it does not
wait for a token and a token cannot cure it.

**Plan.** The follow says `waiting-for-address` for such a project, token or none, and refresh's check of what waits for
a token leaves it out. The interface reads the new state. A test holds it.
