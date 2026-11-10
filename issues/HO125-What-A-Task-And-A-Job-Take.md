# HO125 — What A Task And A Job Take

```json
{
  "$schema": "issue-1.json",
  "id": "HO125",
  "title": "What A Task And A Job Take",
  "state": "Implementing",
  "size": "L",
  "priority": "Medium",
  "rank": 1,
  "blockedBy": [],
  "covers": "The measuring run also reads a task, an agent's fixed start and Maven jobs, so a size can rest on what work takes: the tool for one measuring issue in Porelo."
}
```

**Why this size.** the measuring script learns three steps, each making and taking away what it reads, with their tests, the
role's options and README, and a first run on a local VM.

**2026-11-10:** Its rented run still needs the operator's word, with its price and duration brought to them
first; this round builds the tool and runs it on a local VM.

**What must be true.** `porelo.host.measure` also reads a task, an agent's fixed start, and a Maven build in a job at 1, 2 and 4
parallel jobs and past the half, cold and with the cache, so a size can rest on what work takes and not on an idle host.

## What it is, and what is not here

**The tool for one measuring issue, by the operator's word.** Porelo's own issue on what Core takes now holds the question, how
many developers with about 5 tasks fit on 64 GB and on 128 GB, with and without Forgejo, the two machines, their rental, the
one load and the one table. This issue holds what `porelo.host.measure` must read on a host for that: the placeholders
`task`, `agent` and `job` of `measure_steps`, the throwaway accounts, and past the half with [HO127](README.md#ho127)'s
setting. **The default for parallel jobs** is still its answer: unset, `up` gives 2 jobs within half the host, and that depends
on what runs there.

## What a host without an organization can do, read and not yet run

The setup: `up` in the shapes `room` and `both` with no central, throwaway accounts with throwaway vaults, 5 tasks each,
`porelo-agent-stub` for the mass, developers raised until something suffers, read from the cgroups and PSI.

- **A vault with no input: yes.** `porelo vault init --passphrase-stdin`, then `porelo vault unlock --passphrase-stdin`, one
  line on a pipe and no terminal, as `up` does it.
- **`up` with no organization: as the idle run does.** `up` needs one to follow, so the run stands in one that does not exist,
  signed by a key thrown away, and its follow finds nothing.
- **Accounts: the run makes them itself.** The follow alone makes a person's account, and it finds nobody. So each needs what
  `porelo-host-person` gives: `useradd`, subordinate IDs, linger, and the groups `porelo-people` and, where they exist, `kvm`
  and `libvirt`. That the follow leaves an account with no record alone is to be shown.
- **Tasks in `default`: by the documents, yes.** `porelo` reads only `/etc/porelo-host/forge.conf` and the organization's project
  files of the host, and `default` takes a checkout as its source. `task start --agent stub --no-input --detach`. Five tasks of
  one repository need five names, as a start names the task after the repository.
- **Tasks on the local forge: no.** Without an organization the follow registers no project and makes no forge user, so a row
  with a `central` has nothing to reach. A job's load needs its own project: one repository at the pinned tag, made through
  Forgejo's admin, run by the host's runner. What a gate user takes stays "not measured".
- **The room is overstated.** With no project naming the host's gate, `default`'s conversation is on a homeserver of each
  account's own, as a user unit. A real host has the one gate. Each account's homeserver is read from its own unit and taken
  out, and the table says so.
- **A real agent's start needs a credential.** A start with nothing stored for its agent is refused, so "one real agent idle
  and at a fixed start" needs a token in a throwaway vault on a rented machine: the operator's word, or that row stays "not
  measured".
- **A fixed end of 12 developers may not reach it on 128 GB:** raised until something suffers, not to a number.

**First, on a local VM, before any rental:** one such account, shape `room`, two stub tasks in `default`. It shows the follow,
the names and the homeserver's unit, for about half an hour.

## Why

[HO120](README.md#ho120)'s run reads the machine before `up` and each idle shape, and writes "not measured" for these three. A
task and an agent's start need a person and a vault on the host, and a job needs a project on the forge, none of which the
idle run makes. **Until this is done, a size that has to hold work does not rest on a measured number.**

## Already settled, in HO120's analysis

- **The Maven project:** `porelo-buildtools` at a pinned tag, so the number can be run again. It reaches Maven Central, whose speed
  is in the cold number.
- **An agent:** idle and a fixed start only. Real work stays "not measured", as it needs a token, costs money, and a model's answer varies.
- **More than the half:** 4 jobs on a small machine are refused by `forge`'s capacity check, and showing what happens past it is the
  point. It takes a variable the measuring run alone sets, and it has to reach `up` there. The first one set a variable in a play
  that starts `up` as a separate process, so it never arrived, and it was taken out unused. Pass it on the run's own command line,
  tested not to reach any other `up`. [HO127](README.md#ho127)'s setting replaces that variable, so it comes first.

## What it opens

- **[HO119](README.md#ho119)'s sizes:** each "not measured" there, the rule for parallel jobs, and what a person gives up below a size.
- **`disk_free_gib`** in the check's limits, unset until work's disk is read.

## Plan

- **`task`**, in the shapes `room` and `both`: the run makes throwaway accounts as `porelo-host-person` would
  (`useradd`, subordinate IDs, linger, `porelo-people` and, where they exist, `kvm` and `libvirt`), each with a
  throwaway vault (`vault init` and `unlock --passphrase-stdin`, the passphrase a random one in the run's memory alone),
  a checkout of a local repository, and five `porelo task start --agent stub --no-input --detach` tasks in `default`,
  each named. It reads the accounts' slices: start time, memory peak, CPU time, disk growth; developers are raised 1, 2,
  4 and on until a start fails or memory or CPU pressure (PSI) stays above its line, and the count where it stopped is a
  fact. Each account's own homeserver is read from its unit, named in the facts, and stopped. The accounts go again with
  their homes and linger, and a leftover stops the run as a failed `down` does.
- **`agent`**: stays null with its why until a token is the operator's word on the rented run; `stub`'s fixed start is
  read under `task`.
- **`job`**, in the shapes `forge` and `both`: one project made through Forgejo's admin, one repository holding
  `porelo-buildtools` at a pinned tag with a workflow building it with Maven; 1, 2 and 4 parallel jobs and past the
  half, cold and with the cache, each its wall time and the runner's slices. Past the half goes through
  [HO127](README.md#ho127)'s `porelo_host_work_share` on that `up`'s own command line and no other.
- **`measure_steps`** takes `task` and `job` as measured; the README and argument specs say what each makes and takes
  away.
- **Red first:** with the `Machine` stand-in, each step's facts and its cleanup, a leftover account refused, an account
  made by the run never kept after a failed step, and a share past the half reaching only that `up`.
- **First run:** on a local VM, shape `room`, two stub tasks, about half an hour, before any rental.
