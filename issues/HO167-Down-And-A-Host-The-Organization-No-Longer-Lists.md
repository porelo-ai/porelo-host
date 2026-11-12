# HO167 — Down And A Host The Organization No Longer Lists

```json
{
  "$schema": "issue-1.json",
  "id": "HO167",
  "title": "Down And A Host The Organization No Longer Lists",
  "state": "Accepted",
  "size": "-",
  "priority": "Medium",
  "rank": 4,
  "blockedBy": [],
  "covers": "`down` on a host the organization no longer lists, while persons still hold memberships, names them and asks y/N before it takes them off and goes down; `--force` skips the question, and without a terminal it refuses."
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
person by hand. The rented rehearsal's VM proof met this on 2026-11-10 (run 3 and run 4: `down` exit 2 after the run had taken
the host out). The rehearsal now takes the project off and lets the host follow while it is still listed, then takes it
out, then runs `down` (run 5: all OK). A person doing the same by hand has no such order to follow, and nothing tells
them. Raised by Agent Coordinator for the morning.

**Decided.** `down` on a host that the organization no longer lists, while persons still hold project memberships
other than host-admin:

- warns and names each of those memberships, person and project;
- then asks y/N; on yes it takes them off and goes down, on anything else it changes nothing and exits non-zero;
- with `--force` it skips the question, takes them off and goes down;
- without a terminal and without `--force` it refuses, with words naming the memberships and `--force`.

A host the organization still lists keeps today's refusal and its advice.
