# HO177 — A Job's Own Leg Reaches A Pool VM

```json
{
  "$schema": "issue-1.json",
  "id": "HO177",
  "title": "A Job's Own Leg Reaches A Pool VM",
  "state": "Review",
  "size": "S",
  "priority": "High",
  "rank": 1,
  "blockedBy": [],
  "covers": "In Molecule with the forge and the pool on, a job on the forge's runner runs `porelo-machines acceptance --kind amd64` itself, told the pool by its environment and given the run key as a secret, and its leg passes on a pool VM."
}
```

**Why this size.** one leg in the follow's act, the workflow it pushes and the secret it sets; no role changes.

**What must be true.** A job on the forge's runner, on the image the repositories' workflows use, runs the real
`acceptance --kind amd64` without `--pool`: it takes the pool from `PORELO_MACHINES_POOL`, the run key from the
repository secret `PORELO_POOL_SSH`, reaches a pool VM over the job's own network, runs the leg there and gives the
account back. A host without a pool still tells its jobs nothing.

**Why.** [HO27](README.md#ho27) told every job where the pool is, but its Molecule leg ran as root on the host, so a
job's network reaching a pool VM was never measured. Core's B322 relies on it (story ST40 in porelo-project). Filed on
the coordinator's word.

## Plan

- The act sets the secret `PORELO_POOL_SSH` from the pool's run key through the forge's API, its value never in an
  argument.
- It pushes, beside the workflow, the BT84 tooling the pool leg checked and its leg script; the job fetches its own
  commit's archive from the forge with its job token and runs the leg with the mounted JDK.
- The job runs on `ubuntu-24.04`, a glibc image as the repositories use; the runner's own `porelo-host` image is
  Alpine, where the mounted JDK does not run.
- The act waits for the run and requires `success`; on a host without a pool the job checks the variable is empty, as
  today.

## Acceptance

- Molecule `default` with the forge and the pool on is green, with "a job's own leg to reach a pool VM" among the
  act's facts.

## As built

- Molecule `default` with the forge and the pool on is green (2026-11-12): the job on `ubuntu-24.04` took the pool
  from `PORELO_MACHINES_POOL`, the run key from the secret `PORELO_POOL_SSH`, and its leg passed on a pool VM.
- The first run was red for another reason: one poll of the forge's tasks hung for 400 s while the pool VM ran. Each
  call of the act's `forge` helper is now bounded at 60 s, so a slow answer counts as "not yet" and the poll goes on;
  a red leg names the host's memory and load beside the job's state.
