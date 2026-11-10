# check

`up`'s first task, and what the interface sends by ssh before it installs anything: `files/porelo-host-check`, Python's standard
library alone, as Ansible itself is the first change. It reads and writes no file, and reports every finding at once.
This pre-installation check is one of the four collection script exceptions; it does not need the host package.

## Running it

    ssh <machine> python3 - --limits "$(cat limits.json)" --choices '{"kvm": false, "forge": true}' < porelo-host-check

Choices: `kvm`, `forge`, `jobs`, `job_cpus`, `job_memory`, `pool` (`systems`, `accounts`, `memory`), `ports`, `share_percent`
(`porelo_host_work_share`, unset the limits' half). Each is optional.
`--no-network` leaves the `reach_` findings `unknown`. `files/limits.json`, in the tarball, holds the limits, for an interface comparing an
offer before renting too. The form of the answer is in [What a program reads](../../doc/lines.md).

## What it reads

| `id` | Asked |
| --- | --- |
| `kvm_setting` | a yes or no |
| `root` | root; a login that is not is the interface's to tell, as is a closed root |
| `system` | Ubuntu 26.04 |
| `cloud_init`, `packages_free` | the image has finished; no package run is under way; `up` waits up to 5 minutes for one to end, as Ubuntu starts its own daily, and the interface's one look does not |
| `cpus`, `memory` | the machine says |
| `virtualization` | `vmx` or `svm`, only with `kvm` |
| `cgroup`, `delegated` | cgroup v2's `cpu`, `memory`, `pids`, delegated to a user by systemd's default |
| `route`, `address`, `host_key` | an IPv4 default route, the address it sends from; an ed25519 host key |
| `reach_<host>`, one for each | TCP to what the run fetches from, the machine's own package sources too; nothing is sent, and all share one clock of 10 s |
| `disk` | reported, refusing nothing until a limit is measured |
| `work_share` | only when asked: a whole number of percent from 1 to 100 |
| `pool_shape`, `pool_kvm`, `pool_memory`, `jobs` | the pool and the jobs within the host's share |
| `ports` | what binds on the host itself is free, but for what this host's own forge holds |

## What it cannot know

- That KVM works: a flag does not show a firmware that has it off, and `/dev/kvm` may need a module, loading which is a change. `base` asks KVM after installing.
- The account's own controllers, as the account is made later: `base`'s `controllers` still asks then.
- That a port this host's own forge recorded is still the forge's, on a later `up`: its socket unit says then.
- A store's bucket, as its keys come at the person's step.
- That the packages install, or an image pulls.
- Reach from outside, and how the machine runs under load.

Each role's stop that could only be late, or that can change in between, stays there: see the issue's table.
