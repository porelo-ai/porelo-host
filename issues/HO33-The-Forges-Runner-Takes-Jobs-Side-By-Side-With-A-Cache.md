# HO33 — The Forge's Runner Takes Jobs Side By Side, With A Cache

**Status:** Implementing.
**Size:** M - the role `forge`'s runner configuration and unit, three variables with their argument specs and a
refusal in the style of the VM pool's, Molecule's checks of the written files, and one measurement on a rented host.

**What must be true.** The host's forge runs as many jobs at once as the machine holds within each job's fixed bounds,
not one after another. A job's `actions/cache` reaches the runner's cache, so a second run of a workflow restores what
the first one saved instead of starting cold.

## What was measured

Sprint 5's rented host, `EM-I220E-NVME` (16 cores, 32 threads, 128 GB), porelo-buildtools pull request 1 on
2026-10-27:

- **One job at a time.** The Build of the branch's push ran 07:06:46-07:09:17Z. The pull request's Build started at
  07:09:18Z, and its Shared rules check at 07:11:42Z, each one second after the one before it ended. On GitHub the
  three run side by side. `roles/forge/templates/runner-config.yml.j2` writes `capacity: 1`, and nothing sets it
  otherwise.
- **No cache.** Every `actions/cache` step warned `getCacheEntry failed: connect ECONNREFUSED <host's public
  address>:36613`, and on saving `reserveCache failed` the same way. The configuration has no `cache:` section, so
  runner 13.2.0 starts its internal cache on a random port and builds its URL from the address it detects, the host's
  public one. A job's container cannot reach that address on that port: the runner's container publishes no port.
- **What it costs.** porelo-buildtools' *Build and unit tests* took 151 s on the forge against 127 s on GitHub, with
  every Maven dependency fetched again. The three runs of one commit took five minutes in a row where GitHub took two.

## Plan

- **Capacity:** a new variable `forge_runner_capacity`, default `4`, written as `runner.capacity`. With the job
  bounds' defaults, 4 CPUs and `8g`, four jobs take 16 of the 32 threads and 32 of the 128 GB, beside Forgejo's 2
  CPUs and 2 GB, the runner's 1 CPU and the VM pool.
- **A capacity that does not fit is refused**, before the configuration is written, by the role's own `capacity`
  entry point (`tasks/capacity.yml`), in the style of `roles/vm_pool/tasks/memory.yml`:
  - the rule is one budget with the VM pool (QH39, under *Decided*): `forge_runner_capacity` × `forge_job_cpus` ≤ half the
    host's processors, and `forge_runner_capacity` × `forge_job_memory` plus the pool's VMs ≤ half its `MemTotal`;
  - the other half stays with Forgejo, the runner and Porelo's own tasks;
  - the refusal names both sides;
  - a capacity below 1 is refused as well.
- **The cache reached on the forge's own address:**
  - `runner-config.yml.j2` gains `cache:` with `enabled: true`, `dir: /data/cache` (the runner's volume),
    `host: {{ forge_address }}` and fixed `port` and `proxy_port` from a new variable `forge_runner_cache_port` and
    the one above it.
  - `forgejo-runner.container.j2` publishes both ports on `{{ forge_address }}`, the proxy's for the jobs and the
    server's for the proxy, since the runner names the cache by that address. This is the
    same way Forgejo's port 3000 is published, which jobs already reach: the checkout's header names
    `https://10.73.0.1:3000/`.
  - The `secret` stays empty, so the runner makes a new one at each start. That only invalidates the proxy's tie to
    its own server across a restart, not the stored entries.
- **Down:** the cache lies in the runner account's home, which `down` already takes with the account. The ports
  listen only on the VPN's address, as Forgejo's 3000 does, so the nftables table needs no new rule.
- **Molecule** (`extensions/molecule/default/tasks/resources.yml`):
  - the written configuration holds the capacity and the cache's `host`, `port` and `proxy_port`;
  - the unit publishes both ports on the forge's address only;
  - the `capacity` entry point takes half the test VM's processors and refuses one job per processor; it also
    refuses for memory one job of all the memory, and a pool of half the memory beside one small job
    (`tasks/capacity_refused.yml`), each message naming the host's half;
  - converge gives the test VM job bounds of its size, which the job-options check and the probe job assert.
- **Docs:** the role's README names the three variables, and `doc/index.md` the capacity and the budget, beside the job bounds; changelog under *Added*.

## Acceptance

- Molecule's checks above, each seen red first against today's files.
- Measured on a rented host with the forge, by a push that starts two workflows:
  - the two runs overlap in time;
  - a second push's `actions/cache` step says it restored the cache, and its Build is shorter than the first.

## To be checked

- That a job container reaches `forge_address:<proxy_port>` as it reaches port 3000, under the runner account's
  rootless podman. The plan rests on that.
- Runner 13.2.0's cache keys as named above. They are read from its `config.example.yaml` and its source, not yet run.
- Whether jobs of one workflow, such as the matrix *Snapshot* jobs, lease more from the VM pool when they run side by
  side. Today they never run at once.

## Decided

- **QH36 (a), the operator, 2026-10-27:** `forge_runner_capacity` defaults to `4`, refused above half the machine as
  planned; it is not worked out at `up`.
- **QH39 (a), the operator, 2026-10-27:** one budget with the VM pool. Capacity × job memory plus the pool's VMs
  stays within half the host's memory, and capacity × job CPUs within half its processors. Molecule sets job bounds of
  its own size, and the rented host keeps the defaults. `EM-I220E-NVME` takes them exactly on CPUs (16 of 32 threads).
  The operator's word named capacity 1 and 1g for Molecule. It was built with capacity 2 and 768m (1 CPU, OMP 1),
  so the written capacity differs from the old fixed 1 and the check is red against it. Two such jobs and the pool's
  one VM still fit half the test VM's 6 GiB. The operator agreed to capacity 2 and 768m on 2026-10-27.
