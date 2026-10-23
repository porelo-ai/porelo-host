# HO20 — Every Container Of The Host Fits The Machine

**Status:** Idea.

**What must be true.** Every container and VM the collection starts on a host is bounded so that it runs on a host
of any size, from a small one to 32 cores and more: none of them reaches podman's default `pids_limit` because a pool
grows with the cores, and none is made where the host's memory cannot hold it. It is porelo-host's part of
porelo-project [PJ68](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj68).

## What sets no limit today

- **The forge and its runner**, `roles/forge/templates/forgejo.container.j2` and `forgejo-runner.container.j2`: no
  `PidsLimit=`, no memory and no CPU bound, so podman's defaults apply. Go's runtime takes one OS thread per core
  (`GOMAXPROCS`), which stays far below 2048.
- **The runner's job containers**, through `container.options` in `runner-config.yml.j2`: no `--pids-limit`,
  `--memory` or `--cpus`. A job's build tool sizes its threads from the cores it sees: Maven's `-T 1C`, Gradle's
  workers, a JVM's garbage collector and compiler. That is the same pattern as the room's homeserver, which on a
  32-core host sized a pool of 2048 threads against the 2048 limit and did not start.
- **The VM pool**, `roles/vm_pool`: 1536 MiB and 1 vCPU each, 1 to 8 accounts, so up to 12 GiB beside the host's own
  work. Nothing compares that with the host's memory before the VMs are made.

## To decide, nothing measured

- The bounds for the two quadlets, and whether they are fixed or read from the host's size.
- The job containers' `--pids-limit`, `--memory` and `--cpus`, and whether `--cpus` is what lets a build inside read
  a smaller core count (cgroup v2).
- What the pool's check refuses, and whether it counts the forge and Porelo's tasks beside the VMs.
- A Molecule check that reads each bound from what the role writes, since the test VM's few cores never reach a pool
  that grows with the host.
