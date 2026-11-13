# HO188 — A Host's Task Record Is One Project's

```json
{
  "$schema": "issue-1.json",
  "id": "HO188",
  "title": "A Host's Task Record Is One Project's",
  "state": "Backlog",
  "size": "S",
  "priority": "Medium",
  "rank": 10,
  "blockedBy": [],
  "covers": "The host's documents, its Molecule checks and the measuring role read a task's record and forge token under the project and the task, as porelo's host program keys them once two projects of one person may each have a task of one name."
}
```

**Why this size.** No program of this repository writes the records: porelo's host program does. What is here reads
them or describes them: `doc/task-certificates.md`, the Molecule default scenario's `follow_act.py` and the measuring
role. One module's paths and their tests, once porelo's layout is known.

**What must be true.** A person's task is one project's. Two projects of one person, each with a task `shell` on one
host, have two records and two forge tokens, and ending one leaves the other's record and token. The host's documents
say the record's path and the token's name as porelo's host program keeps them, and the host's checks read them there.

## Why

porelo's host program keys a person's task by login and task name alone. `HostTasks` writes
`/var/lib/porelo-host/tasks/<login>/<task>.json` and issues the forge token `porelo-task-<task>`; its `end(person,
task)` drops both, and the client calls it with the task's name alone. The certificate's principal is
`task:<project>:<task>`, but the end does not check it. So with project A's `shell` and project B's `shell` of one
person on one host, removing A's `shell` ends the host record and drops the forge token of B's running `shell`. The
key that tells the two apart is porelo's to change, in
[B735](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b735); what becomes of records and tokens
under the old key on a running host is the operator's question, asked under
[B246](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b246).

## Plan

- porelo's layout, as its issue above sets it: the record `/var/lib/porelo-host/tasks/<login>/<project>/<task>.json`,
  the forge token `porelo-task-<project>_<task>`, and an end that takes the project and the task. A record under the old
  layout, `tasks/<login>/<task>.json` with the token `porelo-task-<task>`, is still listed and ended; whether a running
  host's old records move at its next update waits on the operator.
- `doc/task-certificates.md`: the record's path, the token's name, and that `--end` names the project.
- `extensions/molecule/default/files/follow_act.py`: the two record paths it reads (around 405 and 583).
- `roles/measure/files/porelo-host-measure` (around 823) and `tests/unit/roles/test_porelo_host_measure.py`: the
  measure's own task records.
- Red first: in Molecule, two projects of one person each start a task `shell`; ending one leaves the other's record
  and token. Its unit part: the measure reads a record under its project.

## Acceptance

- Two projects' tasks of one name of one person each keep their own record and token on the host; the end of one
  leaves the other's.
- The host's documents and checks name the record and the token as porelo's host program keeps them.
