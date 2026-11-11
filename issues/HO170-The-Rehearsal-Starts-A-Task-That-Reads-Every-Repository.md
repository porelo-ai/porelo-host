# HO170 — The Rehearsal Starts A Task That Reads Every Repository

```json
{
  "$schema": "issue-1.json",
  "id": "HO170",
  "title": "The Rehearsal Starts A Task That Reads Every Repository",
  "state": "Estimated",
  "size": "XS",
  "priority": "Medium",
  "rank": 7,
  "blockedBy": [],
  "covers": "The rented host's rehearsal starts one task with porelo's read-all start option and checks that it sees every repository of the project under /workspace, can write none of them, and leaves nothing behind after it ends."
}
```

**Why this size.** It is one more task in the existing `tasks` step, with a short check before and after. There is
no new step, no new contract value and no role change. It is the porelo-host line of ST319, after porelo's B619 ("A
Task Reads Every Repository Of Its Project"), which supplies the start option. HO169 was rejected in its favour.

**What must be true.** On a rented host the rehearsal proves what B619 promises there:
- a task started with every repository of the project, read only, sees each one as `/workspace/<repository>/` at that
  repository's `main`, the project's own repository among them;
- a write under `/workspace` is refused;
- the task has no gate token and no push target;
- after the task ends and is removed, nothing of it is left on the host.

## Plan

1. **Start.** `build/rehearse-steps/tasks` starts a fourth task, `rehearsal-all`, with B619's start option (its CLI
   name as porelo ships it) and no `-r`. It uses the same agent, provider and model as the others and a short prompt
   with no work in it.
2. **Read.** Through `REHEARSAL_PERSON_SSH`, the step lists `/workspace/` inside the task. There must be one directory
   per repository the project's file names, plus the project's own. Each one's `HEAD` must be the commit the host's
   mirror holds for that `main`.
3. **Write.** A `touch` under `/workspace/<first repository>/` must fail. `git push` from it must have no remote to go
   to.
4. **End.** The step stops and removes `rehearsal-all`. No container, volume or workspace of it may remain, and its
   durable record stays.
5. **Older porelo.** While the host's porelo refuses the start option as unknown, the part is SKIPPED with porelo's
   own words. The step goes on with the other tasks, so the rehearsal stays green on an older snapshot.
6. **Docs.** `doc/testing.md`'s list of what the `tasks` step proves gets the line.

The step is a rehearsal script, so a VM run of the rehearsal is its proof. It is not built until B619's code is on
porelo's `main`. Then the next rehearsal run carries it.
