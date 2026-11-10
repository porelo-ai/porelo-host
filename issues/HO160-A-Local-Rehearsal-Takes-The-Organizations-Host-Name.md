# HO160 — A Local Rehearsal Takes The Organization's Host Name

```json
{
  "$schema": "issue-1.json",
  "id": "HO160",
  "title": "A Local Rehearsal Takes The Organization's Host Name",
  "state": "Idea",
  "size": "-",
  "priority": "Medium",
  "rank": 1,
  "blockedBy": [],
  "covers": "Bug: a local rehearsal with a real organization's machine file runs `up` under that host's name, not `rehearsal`, so its fetch takes the pin."
}
```

**What must be true.** `build/rehearse-move.sh start --machine-file` runs `up` under the host's name in the given
organization, so the host's fetch reads that host's files and takes its pin. Today every local VM is named
`rehearsal`, and with a real organization's machine file the fetch refuses with "no commit on this host's files is
signed for the pin" until the inventory's `porelo_host_name` is changed by hand and `up` runs again.

## Acceptance

- A start with a machine file for a host named in the organization follows it on the first `org refresh`.
- A start with a machine file and no host name, or one the organization does not list, is refused before the VM is
  made.
