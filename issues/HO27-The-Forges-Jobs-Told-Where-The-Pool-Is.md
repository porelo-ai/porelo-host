# HO27 — The Forge's Jobs Told Where The Pool Is

```json
{
  "$schema": "issue-1.json",
  "id": "HO27",
  "title": "The Forge's Jobs Told Where The Pool Is",
  "state": "Estimated",
  "size": "M",
  "priority": "Medium",
  "rank": 26,
  "blockedBy": [],
  "covers": "The forge's runner tells every job where the VM pool is, so one workflow takes a pool account on the forge and rents a server on GitHub."
}
```

**What must be true.** One workflow, unchanged on GitHub and on the host's forge, rents a test machine of a kind:
on the forge it takes a run account of the host's VM pool, on GitHub a rented server. The forge's runner tells
every job where the pool is, `PORELO_MACHINES_POOL=/etc/porelo-host/pool/pool.json`, wherever the pool is on;
on GitHub the variable does not exist.

## Why

- `porelo-machines acceptance` takes the pool only from `--pool <file>`, so a workflow that should use the pool on the
  forge would differ from its GitHub copy.
- The pool's file is mounted read-only into every job and its run key is the organization's secret `PORELO_POOL_SSH`
  ([HO12](README.md#ho12)), sent into each project's organization; `acceptance --kind` exists; beyond those, only
  the switch is missing.
- It needs, in porelo-buildtools: `acceptance` reading `PORELO_MACHINES_POOL` when `--pool` is not given, empty
  counting as unset, and `sweep --mine` doing nothing where the job rented from the pool.
- No repository built on the forge rents an `amd64` machine yet.

## Plan

Read in porelo-host 8133028 and porelo-buildtools 1f48368:

- **Here (XS).** `roles/forge/templates/runner-config.yml.j2` adds
  `--env=PORELO_MACHINES_POOL=/etc/porelo-host/pool/pool.json` beside the pool's volume, under the same
  `porelo_host_vm_pool is defined`; `tests/unit/roles/test_forge_runner_transport.py` renders it with and without a
  pool, seen red first; `roles/forge/README.md`, `doc/local-forge.md` and the changelog say it.
- **In porelo-buildtools (S, its BT84).** `acceptance` takes `PORELO_MACHINES_POOL` when `--pool` is
  not given, empty counting as unset, and `--accounts` above 1 stays refused with it as with `--pool`; `sweep --mine`
  with the variable set and no provider token says that nothing was rented from a provider and exits 0, where today it
  stops on the missing token. Each seen red first in `MainTest`.
- **The Molecule proof (S).** Today `extensions/molecule/default/tasks/pool.yml` runs `acceptance --pool` as root on the
  host, not from a job. The acceptance needs a job on the forge's runner: a workflow in the follow's repository that
  runs `acceptance --kind amd64` without `--pool`, with the mounted JDK and the checked tooling, so a job's network
  reaching a pool VM is measured for the first time.
- **Order and size.** porelo-buildtools first, then here; XS 8 + S 27 + S 27, about 62 min, so M.

## Decided by the operator (2026-11-12)

- **Built now.** B322 waits for it and decides itself how its four accounts map onto pool accounts. porelo-buildtools'
  part is its BT84, which comes first. Plan and size stay: M, about 62 min.

## Acceptance

- In Molecule with forge and pool on, a job on the forge's runner sees the variable and its leg takes a pool account
  by kind; on GitHub the same workflow rents a server.
