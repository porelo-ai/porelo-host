# HO20 — Every Container Of The Host Fits The Machine

**Status:** Implementing.
**Size:** M - two quadlets, the runner's job options, a check of the account's delegated controllers in `base`, and
one in the pool's role, each read in Molecule from what the role writes. Built before release 0.6's sprint 4, the
host's local forge.

**What must be true.** Every container and VM the collection starts on a host is bounded so that it runs on a host
of any size, from a small one to 32 cores and more: none of them reaches podman's default `pids_limit` because a pool
grows with the cores, and none is made where the host's memory cannot hold it. It is porelo-host's part of
porelo-project [PJ68](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj68).

## Plan

- **What sets no limit today**, read in today's code:
  - `roles/forge/templates/forgejo.container.j2` and `forgejo-runner.container.j2` set no `PidsLimit=`, `Memory=` or
    CPU bound, so podman's defaults apply.
  - `roles/forge/templates/runner-config.yml.j2`'s `container.options` sets no `--pids-limit`, `--memory` or
    `--cpus` for a job; `capacity: 1` runs one job at a time.
  - `roles/vm_pool` makes 1 to 8 VMs of 1536 MiB and 1 vCPU and compares that with nothing.
- **What a bound does in a rootless container**, measured for porelo's tasks on the Ubuntu VM: `--cpus` limits time
  but leaves `nproc` at the host's count; `--cpuset-cpus` is refused rootless, since only `cpu memory pids` are
  delegated; `OMP_NUM_THREADS=<n>` makes `nproc` read `<n>`, and a JVM reads the CPU quota itself. Open files are
  524288 already. So a job is bounded by quota and told its cores by `OMP_NUM_THREADS`, as porelo's tasks are.
- **A job, like a task:** `container.options` gains `--cpus=4 --memory=8g --pids-limit=2048 --env=OMP_NUM_THREADS=4`,
  porelo's fixed defaults for a task, not read from the host's size, so a build sees four cores on any host and stays
  below its 2048 processes.
  The job image's `nproc` (BusyBox) ignores `OMP_NUM_THREADS`, so a job reads the variable and its cgroup's `cpu.max`.
- **The forge and the runner's daemon:** `PidsLimit=`, `Memory=` and `CPUQuota=` in each quadlet, fixed values
  (forge `PidsLimit=1024`, `Memory=2G`; runner daemon `PidsLimit=256`, `Memory=512M`): their Go runtimes take a
  thread per core, far below those.
- **The controllers:** `base` reads `systemctl show user@<uid>.service -p DelegateControllers` for Porelo's account and
  the forge's two accounts, and stops `up` naming the account and the controller when `cpu`, `memory` or `pids` is
  missing, since without them every bound above is silently ignored.
- **The pool:** before it makes its VMs, `vm_pool` reads `MemTotal` and stops `up` when the pool's memory
  (`accounts × vm_pool_memory`) is more than half of it, naming both; the forge, one job and porelo's tasks, each
  bounded, share the other half.
- **Red first, in Molecule's verify:** each bound read back from the quadlet and the runner's config the role wrote,
  and from `podman inspect` of the running forge; the controller check run against an account given a drop-in that
  leaves `pids` out, which must stop `up` naming it; the pool's check against a pool sized past the test VM's memory.
- **`doc/index.md`** names the bounds and the two refusals.

## Acceptance

- On the test VM, the forge's and the runner's containers and a job's container report the bounds above in
  `podman inspect`, and a job reads `OMP_NUM_THREADS=4` and a `cpu.max` of four cores.
- `up` stops naming the account and the controller when `pids` is not delegated, and naming the pool's and the host's
  memory when the pool is too large.

## To be checked

- That a job container started by the runner takes `--pids-limit` and `--memory` from `container.options` under
  rootless podman, read with `podman inspect` on the test VM.
- That `DelegateControllers` reads the same on Ubuntu 26.04 for an account with linger and no login session.
