# HO27 — The Forge's Jobs Told Where The Pool Is

**Status:** Idea. It waits for `porelo-machines acceptance --kind <kind>` in porelo-buildtools.

**What must be true.** One workflow, unchanged on GitHub and on the host's forge, rents a test machine of a kind:
on the forge it takes a run account of the host's VM pool, on GitHub a rented server. The forge's runner tells
every job where the pool is, `PORELO_MACHINES_POOL=/etc/porelo-host/pool/pool.json`, wherever the pool is on;
on GitHub the variable does not exist.

## Why

- `porelo-machines acceptance` takes the pool only from `--pool <file>`, so a workflow that should use the pool on the
  forge would differ from its GitHub copy.
- The pool's file is mounted read-only into every job and its run key is the organization's secret `PORELO_POOL_SSH`
  ([HO12](README.md#ho12)); only the switch is missing.
- It needs, in porelo-buildtools: `acceptance` reading `PORELO_MACHINES_POOL` when `--pool` is not given, empty
  counting as unset, and `sweep --mine` doing nothing where the job rented from the pool.
- No repository built on the forge rents an `amd64` machine yet; the first is porelo-frontend's leased leg.

## Acceptance

- In Molecule with forge and pool on, a job on the forge's runner sees the variable and its leg takes a pool account
  by kind; on GitHub the same workflow rents a server.
