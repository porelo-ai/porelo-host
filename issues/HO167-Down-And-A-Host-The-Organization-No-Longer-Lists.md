# HO167 — Down And A Host The Organization No Longer Lists

```json
{
  "$schema": "issue-1.json",
  "id": "HO167",
  "title": "Down And A Host The Organization No Longer Lists",
  "state": "Idea",
  "size": "-",
  "priority": "Medium",
  "rank": 4,
  "blockedBy": [],
  "covers": "Question: whether `down` should refuse a host whose persons still hold project memberships, and what takes those memberships off a host the organization no longer lists, since such a host does not follow the organization any more."
}
```

**What must be true.** The product question has an answer, written here. When a host leaves the organization, either
`down` takes it as it stands, or the host's own follow takes the persons' project memberships off. Today the two do
not fit together:

- `down` refuses while any person holds a membership other than host-admin: "people still hold memberships on this
  host … use "Take the project off" … or "Purge"".
- `porelo-host org follow` on a host the organization no longer lists ends with "the organization has no such host"
  and changes nothing, so its memberships stay.

So a host taken out of the organization before its project comes off it cannot go down until someone purges each
person by hand. The VM proof of [HO158](README.md#ho158) met this on 2026-11-10 (run 3 and run 4: `down` exit 2 after the run had taken
the host out). The rehearsal now takes the project off and lets the host follow while it is still listed, then takes it
out, then runs `down` (run 5: all OK). A person doing the same by hand has no such order to follow, and nothing tells
them. Raised by Agent Coordinator for the morning.

**Open:** whether the follow of a host that is no longer listed should end its memberships (the organization's word
that it is out), whether `down` should say which order works, or both.
