# HO170 — The Rehearsal Starts A Task That Reads Every Repository

```json
{
  "$schema": "issue-1.json",
  "id": "HO170",
  "title": "The Rehearsal Starts A Task That Reads Every Repository",
  "state": "Backlog",
  "size": "XS",
  "priority": "Medium",
  "rank": 7,
  "blockedBy": [],
  "covers": "The rented host's rehearsal starts one task with porelo's read-all start option and checks that it sees every repository of the project under /workspace, can write none of them, and leaves nothing behind after it ends."
}
```

**Why this size.** It is one more task in the existing `tasks` step, with a short check before and after. There is no
new step, no new contract value and no role change. It is the porelo-host line of ST319, after porelo's B619 ("A Task
Reads Every Repository Of Its Project"), which supplies the start option. [HO169](README.md#ho169) was rejected in its
favour.

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
2. **Read.** On the host, the step lists `/workspace/` inside the task's container. There must be one non-empty
   directory per repository `porelo project show` names, the project's own among them. B619 gives each one as a tree
   without `.git`, so no `HEAD` can be compared; the check is that `.git` is absent.
3. **Write.** A `touch` under `/workspace/<first repository>/` must fail. No directory has a git remote, and the
   task's environment names no variable for a gate or a push.
4. **End.** The step stops and removes `rehearsal-all`. No container, volume or workspace of it may remain, and its
   durable record stays.
5. **Older porelo.** While the host's porelo refuses the start option as unknown, the part is SKIPPED with porelo's
   own words. The step goes on with the other tasks, so the rehearsal stays green on an older snapshot.
6. **Docs.** `doc/testing.md`'s list of what the `tasks` step proves gets the line.

**How far it got.** Steps 1 to 6 are on `main` (0af0afc), and a local VM's rehearsal against Core's local build
of B619 (aa7d65c3) showed `rehearsal-all` reading foo-1, foo-2 and foo-project, its write refused and nothing left
after its removal. Left: the reading by another model and the hand-over to Review; no work lies on a branch.

The step is a rehearsal script, so a VM run of the rehearsal is its proof. It is proven against Core's local build of
B619, handed over with its sha256, not against porelo's `main`.
