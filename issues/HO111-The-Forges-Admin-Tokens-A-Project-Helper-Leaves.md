# HO111 — The Forge's Admin Tokens A Project Helper Leaves

```json
{
  "$schema": "issue-1.json",
  "id": "HO111",
  "title": "The Forge's Admin Tokens A Project Helper Leaves",
  "state": "Idea",
  "size": "-",
  "priority": "Medium",
  "rank": 31,
  "blockedBy": [],
  "covers": "A run of the project helper leaves no lasting admin token on the host's forge"
}
```

**What must be true.** A run of the project helper leaves no admin token on the host's forge. Today each run that
reaches the forge's API makes a `porelo-host-project-…` token with `write:admin`, and nothing deletes it: its value is
thrown away, so no one can use it, but the rows grow with every project put on or taken off, and the documents say it
stays in memory.
