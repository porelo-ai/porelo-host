# HO186 — The Measuring Run Reads Jobs And Raises Developers

```json
{
  "$schema": "issue-1.json",
  "id": "HO186",
  "title": "The Measuring Run Reads Jobs And Raises Developers",
  "state": "Backlog",
  "size": "L",
  "priority": "Medium",
  "rank": 7,
  "blockedBy": ["HO187"],
  "covers": "The measuring run reads a Maven build in a forge job at 1, 2 and 4 parallel jobs and past the half, cold and with the cache; raises developers until a start fails or pressure stays high; keeps an agent's fixed start null until a token is the operator's word; and a run on a local VM reads numbers."
}
```

**Why this size.** a project made through Forgejo's admin with a pinned workflow, the parallel and past-the-half
runs with their cache, the raising loop over PSI, each with its cleanup and tests, and a VM run.

**What must be true.** [HO125](README.md#ho125)'s plan, past what it built: `porelo-host-measure` reads what a job
takes and how many developers a host holds, so a size can rest on what work takes.

## Plan

- **`job`**, in the shapes `forge` and `both`: one project made through Forgejo's admin, one repository holding
  `porelo-buildtools` at a pinned tag with a workflow building it with Maven; 1, 2 and 4 parallel jobs and past the
  half, cold and with the cache, each its wall time and the runner's slices. Past the half goes through
  [HO127](README.md#ho127)'s `porelo_host_work_share` on that `up`'s own command line and no other.
- **Developers raised** in `task`: 1, 2, 4 and on, each with five stub tasks, until a start fails or memory or CPU
  pressure (PSI) stays above its line; the count where it stopped is a fact. Each account's own homeserver is read
  from its unit, named in the facts, and stopped.
- **`agent`** stays null with its reason until a token is the operator's word on a rented run.
- **Red first:** with the `Machine` stand-in, each step's facts and its cleanup, a leftover account refused, and a
  share past the half reaching only that `up`.
- **A VM run that reads numbers:** on a local VM, through the coordinator, `task` with the stub from its folder, then
  `job`; the result file kept beside this issue's record.

## Acceptance

- A local VM run's result file holds non-null `task` and `job` facts for every sample, or a null with the reason of a
  step that was refused.
- The raising stops on its own and names the count; nothing the run made is left after it.

## Built so far (2026-11-13)

- **The `job` step.** `porelo-host-measure --steps job` brings the host up in the forge's shape alone for each of 1, 2
  and 4 jobs and 4 past the half (`porelo_host_work_share` 90 on that `up` only); a count the capacity check refuses
  is null with that refusal. The forge's admin, through the forge's socket with its token on curl's standard input,
  carries `porelo-buildtools` onto the forge and branches it at `v0.5.1`, checked against the commit the tag names. A
  workflow of N parallel Maven builds on `ubuntu-24.04` with the count's own cache runs cold, then with the cache.
  Each keeps its wall time (until every part has ended), the runner's CPU, and its memory peak on the cold run. The
  repository goes after each count, and the host goes down.
- **Its tests.** Five unit tests over the stand-in: every count's runs and plays, the refused count, a failed build
  null with the repository still removed, the workflow's YAML, and the token never on a command line. The forge's
  task list grows a part a poll there, so a run is not counted done early.
- **Developers raised.** `--raise` (role option `measure_raise`): after the `task` samples, one more `up`, developers
  `porelo-measure-1` and on raised 1, 2, 4 and on to 32, five stub tasks each. After each level, memory is let settle
  and the kernel's pressure is read twice, half a minute apart. The raising stops at a failed start, or at memory
  pressure of 10% or CPU pressure of 80% that stays. `developers` keeps the last level that held, and `work` says why
  it stopped; where no level held, or the kernel tells no pressure, it is null with that reason. Every developer is
  tried and the host goes down even when one stays, which then ends the run. `--raise` without `task` is refused.
  Seven unit tests: stopped by pressure, by a refused start, every level held, no pressure told, a developer that
  stays, the word alone refused, and none without the word.
- **Each account's own homeserver.** After its starts, each throwaway developer's `porelo-matrix-homeserver.service`
  is read as the developer (`MemoryCurrent`), kept as `memory.current` of "developer's own homeserver", and stopped
  before the developer's slice is read, in the samples and in the raising; one that never ran is null with that
  reason. Two unit tests, and the raising test checks each raised one's is stopped.
- **The first VM run (2026-11-13), at 6f28b6d.** The `task` step's first developer and the raising step's first one
  were refused at their first start: the machine is a host, and a host starts no task without a certificate signed
  by a person of its applied organization. The measuring run's stand-in organization admits nobody, so the host's
  test mode, [HO187](README.md#ho187), has to come first. The `job` step ran on.
  Every build of the `job` step ended in failure, and the jobs' logs went with each count's repository.
- **A failed job's log kept in its reason.** The reason of a failed build ends with the last two lines of its first
  failed job's own log, read as root from the forge's volume (`actions_log`, plain or zstd) before the repository
  goes, without times, colours or unprintable characters. One unit test over the stand-in's log.
- **Not yet:** the VM run that reads numbers for `task`, the raising and `job`.
