# HO128 — A Task's Login Cannot Approve Or Merge

```json
{
  "$schema": "issue-1.json",
  "id": "HO128",
  "title": "A Task's Login Cannot Approve Or Merge",
  "state": "Idea",
  "size": "-",
  "priority": "Medium",
  "rank": 7,
  "blockedBy": [],
  "covers": "A task's gate login on the forge can neither approve nor merge a pull request on `main`, by the forge's own rule, not only because the task never holds its token."
}
```

**What must be true.** A task's gate login on the host's forge, `porelo-<login>`, can neither approve nor merge a pull
request on a protected `main`, by the forge's own rule. Today each follow puts that login into the project's
`developers` team, which is on the approval and merge lists, and a task's token belongs to it with `write:repository`;
what keeps a task from approving or merging is only that the box never holds the token and the gate offers no route to
the forge's API. Only persons in the owners and developers teams may approve or merge; the gate and agent logins push
their branches and open pull requests, nothing more.
