# Which server for what

**This page says what is measured so far, and that is an idle host.** It is not yet a size for a host that has work to do: what a task, an agent and a build
take is "not measured", so nothing below recommends a machine for them.

## What to take

| You will run | System | CPUs | Memory | Disk | KVM |
| --- | --- | --- | --- | --- | --- |
| Tasks only, with a central forge and no Forgejo | Ubuntu 26.04 | not measured | not measured | not measured | no |
| Forgejo and parallel builds | Ubuntu 26.04 | not measured | not measured | not measured | no |
| Forgejo with a VM pool, or a job that makes a VM | Ubuntu 26.04 | not measured | not measured | not measured | yes, `porelo_host_kvm: true` |

What a person gives up below a size is "not measured" too, as no size holds yet.

**The one thing measured: an idle host.** By default `up` brings the room, so tasks only reads as `room`, and Forgejo as `both`; `none` and `forge` have the room turned off, which only the
measuring run does. Each has tasks' software, no person, no project and no task. **These figures are no lower bound:** what `up` takes while it runs is not read, and no KVM or VM pool was on.
All came up on a VM given 4 GiB, which shows 3910 MiB, with 4 CPUs. No run tried less. All three files are local VMs on one machine, differing only in memory.

<!-- sizes:start -->

| Machine | Its memory | Shape | In use, idle | Disk used at `/`, idle |
| --- | --- | --- | --- | --- |
| local-vm-16g | 15988 MiB | `none` | 228 to 229 MiB | 3.5 GiB |
| local-vm-16g | 15988 MiB | `room` | 289 to 290 MiB | 3.6 GiB |
| local-vm-16g | 15988 MiB | `forge` | 377 to 379 MiB | 4.3 GiB |
| local-vm-16g | 15988 MiB | `both` | 435 to 446 MiB | 4.5 GiB |
| local-vm-4g | 3910 MiB | `none` | 230 MiB | 3.4 to 3.5 GiB |
| local-vm-4g | 3910 MiB | `room` | 291 MiB | 3.6 GiB |
| local-vm-4g | 3910 MiB | `forge` | 378 to 379 MiB | 4.3 GiB |
| local-vm-4g | 3910 MiB | `both` | 439 to 442 MiB | 4.5 GiB |
| local-vm-8g | 7936 MiB | `none` | 228 MiB | 3.5 GiB |
| local-vm-8g | 7936 MiB | `room` | 289 to 290 MiB | 3.6 GiB |
| local-vm-8g | 7936 MiB | `forge` | 377 to 378 MiB | 4.3 GiB |
| local-vm-8g | 7936 MiB | `both` | 439 to 448 MiB | 4.5 GiB |

<!-- sizes:end -->

## Parallel builds

**The rule today, not yet measured:** unset, 2 jobs when two of the smallest, 1 CPU and 768 MiB each, fit within half the host beside the VM pool, otherwise 1, each up to 4 CPUs and 8 GiB.
When not even one fits, `up` refuses. So the job count stops at 2. `forge_runner_capacity`, `forge_job_cpus` and `forge_job_memory` set it otherwise, within the same half.
**The half is a setting:** `porelo_host_work_share`, the percent of the host's processors and memory the jobs and the VM pool may take together, from 1 to 100, unset 50.
Above 50 `up` says so, as Forgejo, the runner and the tasks then keep less than half; it protects nothing but the host's own work, so going past it is the operator's choice. Whether 2 and a
half are right, and what happens to tasks past them, is "not measured".

## What `up` tells you early

`up` checks the machine before it installs anything, Ansible itself being the one change before that. In a person's words, it refuses:

- a system other than Ubuntu 26.04, or a run that is not root;
- an image still finishing its first start, or a package run under way;
- a machine without cgroup v2's controllers delegated by systemd, an IPv4 default route with its address, or an ed25519 host key;
- no `vmx` or `svm`, where you asked for KVM;
- a host it cannot reach what it fetches from, or a port it needs taken by anything but this host's own forge;
- a VM pool and jobs asking together more than the host's share, a pool without Forgejo or KVM, or a pool's shape it does not know.

Some things only show later, and `up` stops there: that KVM really works, an account's own controllers, root's key.

**It reports free disk and refuses nothing for it:** no measured number holds yet, as idle says nothing of what work fills. The [check's README](https://github.com/porelo-ai/porelo-host/tree/main/roles/check) has
each finding by name.

## Measured machines

Each table below is made from one file.

The measuring run is the playbook `porelo.host.measure`, run on a fresh machine that is given back; the
[role's README](https://github.com/porelo-ai/porelo-host/tree/main/roles/measure) says its options and what it changes. Check a result for private
names, copy it to `doc/measures/`, and run `python3 build/measure-tables.py`; `--check` refuses tables that differ from the files.

**Each shape is measured from a settled state:** `none` has neither a forge nor a room, `room` has the Matrix homeserver, `forge` has Forgejo and
its runner, `both` has them all. Each reading is one `up`, a settled read, and one `down`, and all three stand here, with no average. Packages and the JDK
stay between readings and between shapes, so a shape's first reading installs what it adds and later ones do not. A `down` removes the forge's accounts with
their images, so every reading of `forge` and `both` fetches them again.

**In use** is the kernel's anonymous memory, summed over the top slices: what the machine cannot simply give back. **With page cache** is what its
cgroups hold besides, which the kernel gives back when asked, so it says little of what a machine needs. In use includes the measuring run itself and
the login it was started from, and an account's own memory is part of it, so the columns do not add up. A dash: the shape has no such account. Disk used is the whole file system's.

**What these do not say.** They are idle numbers on local VMs, with the CPUs each table names and a 20 GiB virtual disk: they show memory and disk, not a real host's time. They do not
read what an `up` itself takes while it runs, and a job or a task needs more on top: tasks, agents and jobs are "not measured", as each table says, so a size
that has to hold work does not rest on them.

<!-- measures:start -->

### local-vm-16g

local local-vm-16g: 4 CPUs of AMD Ryzen AI 7 PRO 350 w/ Radeon 860M, 15988 MiB, ubuntu 26.04, `/dev/kvm` answers: True; collection 0.5.11-snapshot, from snapshots.

| Shape | Reading | `up` took | In use | With page cache | Forge's account | Runner's account | Homeserver's account | Disk used at `/` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| before | first |  | 223 MiB | 1617 MiB | - | - | - | 2.7 GiB |
| before | second |  | 226 MiB | 1620 MiB | - | - | - | 2.7 GiB |
| before | third |  | 226 MiB | 1620 MiB | - | - | - | 2.7 GiB |
| none | first | 111 s | 228 MiB | 2489 MiB | - | - | - | 3.5 GiB |
| none | second | 23 s | 228 MiB | 2489 MiB | - | - | - | 3.5 GiB |
| none | third | 29 s | 229 MiB | 2489 MiB | - | - | - | 3.5 GiB |
| room | first | 69 s | 289 MiB | 2724 MiB | - | - | 60 MiB | 3.6 GiB |
| room | second | 81 s | 290 MiB | 2727 MiB | - | - | 60 MiB | 3.6 GiB |
| room | third | 65 s | 289 MiB | 2727 MiB | - | - | 60 MiB | 3.6 GiB |
| forge | first | 103 s | 377 MiB | 3577 MiB | 118 MiB | 29 MiB | - | 4.3 GiB |
| forge | second | 76 s | 379 MiB | 3579 MiB | 119 MiB | 28 MiB | - | 4.3 GiB |
| forge | third | 88 s | 378 MiB | 3581 MiB | 118 MiB | 29 MiB | - | 4.3 GiB |
| both | first | 142 s | 435 MiB | 3766 MiB | 115 MiB | 29 MiB | 59 MiB | 4.5 GiB |
| both | second | 164 s | 440 MiB | 3773 MiB | 120 MiB | 29 MiB | 59 MiB | 4.5 GiB |
| both | third | 123 s | 446 MiB | 3779 MiB | 122 MiB | 29 MiB | 62 MiB | 4.5 GiB |

What the run left: packages.added: aardvark-dns, acl, buildah, catatonit, conmon, containers-storage, cpp, cpp-15, cpp-15-x86-64-linux-gnu, cpp-x86-64-linux-gnu, criu, crun, dns-root-data, dnsmasq-base, fuse-overlayfs, gcc-15-base, golang-github-containers-common, golang-github-containers-image, libcompel1, libcriu2, libisl23, libmpc3, libnet9, libprotobuf-c1, libslirp0, libsubid5, libyajl2, netavark, passt, podman, porelo, porelo-adapter-forgejo, porelo-agent-agy, porelo-agent-claude, porelo-agent-codex, porelo-agent-omp, porelo-agent-pi, porelo-matrix-homeserver, porelo-message-sluice-filter, porelo-message-transport-matrix, python3-protobuf, python3-pycriu, slirp4netns, uidmap; units.added: netavark-dhcp-proxy.service, netavark-dhcp-proxy.socket, netavark-firewalld-reload.service, podman-auto-update.service, podman-auto-update.timer, podman-clean-transient.service, podman-kube@.service, podman-restart.service, podman-user-wait-network-online.service, podman.service, podman.socket, porelo-host-firewall.service, porelo-host-task-sweep.service, porelo-host-task-sweep.timer, porelo-matrix-homeserver.service, porelod.service; accounts.added: dnsmasq.

Not measured: agent, job, task.

### local-vm-4g

local local-vm-4g: 4 CPUs of AMD Ryzen AI 7 PRO 350 w/ Radeon 860M, 3910 MiB, ubuntu 26.04, `/dev/kvm` answers: True; collection 0.5.11-snapshot, from snapshots.

| Shape | Reading | `up` took | In use | With page cache | Forge's account | Runner's account | Homeserver's account | Disk used at `/` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| before | first |  | 223 MiB | 1617 MiB | - | - | - | 2.7 GiB |
| before | second |  | 228 MiB | 1622 MiB | - | - | - | 2.7 GiB |
| before | third |  | 228 MiB | 1623 MiB | - | - | - | 2.7 GiB |
| none | first | 65 s | 230 MiB | 2489 MiB | - | - | - | 3.4 GiB |
| none | second | 26 s | 230 MiB | 2490 MiB | - | - | - | 3.5 GiB |
| none | third | 20 s | 230 MiB | 2491 MiB | - | - | - | 3.5 GiB |
| room | first | 38 s | 291 MiB | 2727 MiB | - | - | 59 MiB | 3.6 GiB |
| room | second | 48 s | 291 MiB | 2726 MiB | - | - | 60 MiB | 3.6 GiB |
| room | third | 48 s | 291 MiB | 2728 MiB | - | - | 59 MiB | 3.6 GiB |
| forge | first | 136 s | 378 MiB | 3391 MiB | 117 MiB | 28 MiB | - | 4.3 GiB |
| forge | second | 131 s | 378 MiB | 3430 MiB | 117 MiB | 29 MiB | - | 4.3 GiB |
| forge | third | 87 s | 379 MiB | 3340 MiB | 118 MiB | 29 MiB | - | 4.3 GiB |
| both | first | 98 s | 440 MiB | 3366 MiB | 121 MiB | 29 MiB | 56 MiB | 4.5 GiB |
| both | second | 147 s | 442 MiB | 3439 MiB | 118 MiB | 29 MiB | 62 MiB | 4.5 GiB |
| both | third | 113 s | 439 MiB | 3403 MiB | 116 MiB | 29 MiB | 60 MiB | 4.5 GiB |

What the run left: packages.added: aardvark-dns, acl, buildah, catatonit, conmon, containers-storage, cpp, cpp-15, cpp-15-x86-64-linux-gnu, cpp-x86-64-linux-gnu, criu, crun, dns-root-data, dnsmasq-base, fuse-overlayfs, gcc-15-base, golang-github-containers-common, golang-github-containers-image, libcompel1, libcriu2, libisl23, libmpc3, libnet9, libprotobuf-c1, libslirp0, libsubid5, libyajl2, netavark, passt, podman, porelo, porelo-adapter-forgejo, porelo-agent-agy, porelo-agent-claude, porelo-agent-codex, porelo-agent-omp, porelo-agent-pi, porelo-matrix-homeserver, porelo-message-sluice-filter, porelo-message-transport-matrix, python3-protobuf, python3-pycriu, slirp4netns, uidmap; units.added: netavark-dhcp-proxy.service, netavark-dhcp-proxy.socket, netavark-firewalld-reload.service, podman-auto-update.service, podman-auto-update.timer, podman-clean-transient.service, podman-kube@.service, podman-restart.service, podman-user-wait-network-online.service, podman.service, podman.socket, porelo-host-firewall.service, porelo-host-task-sweep.service, porelo-host-task-sweep.timer, porelo-matrix-homeserver.service, porelod.service; accounts.added: dnsmasq.

Not measured: agent, job, task.

### local-vm-8g

local local-vm-8g: 4 CPUs of AMD Ryzen AI 7 PRO 350 w/ Radeon 860M, 7936 MiB, ubuntu 26.04, `/dev/kvm` answers: True; collection 0.5.11-snapshot, from snapshots.

| Shape | Reading | `up` took | In use | With page cache | Forge's account | Runner's account | Homeserver's account | Disk used at `/` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| before | first |  | 223 MiB | 1616 MiB | - | - | - | 2.7 GiB |
| before | second |  | 226 MiB | 1619 MiB | - | - | - | 2.7 GiB |
| before | third |  | 226 MiB | 1619 MiB | - | - | - | 2.7 GiB |
| none | first | 70 s | 228 MiB | 2488 MiB | - | - | - | 3.5 GiB |
| none | second | 21 s | 228 MiB | 2489 MiB | - | - | - | 3.5 GiB |
| none | third | 23 s | 228 MiB | 2489 MiB | - | - | - | 3.5 GiB |
| room | first | 39 s | 290 MiB | 2727 MiB | - | - | 59 MiB | 3.6 GiB |
| room | second | 37 s | 290 MiB | 2729 MiB | - | - | 60 MiB | 3.6 GiB |
| room | third | 44 s | 289 MiB | 2725 MiB | - | - | 60 MiB | 3.6 GiB |
| forge | first | 147 s | 377 MiB | 3575 MiB | 118 MiB | 29 MiB | - | 4.3 GiB |
| forge | second | 153 s | 378 MiB | 3580 MiB | 119 MiB | 28 MiB | - | 4.3 GiB |
| forge | third | 92 s | 377 MiB | 3579 MiB | 118 MiB | 29 MiB | - | 4.3 GiB |
| both | first | 105 s | 439 MiB | 3769 MiB | 119 MiB | 28 MiB | 61 MiB | 4.5 GiB |
| both | second | 103 s | 448 MiB | 3816 MiB | 119 MiB | 29 MiB | 60 MiB | 4.5 GiB |
| both | third | 101 s | 446 MiB | 3814 MiB | 119 MiB | 29 MiB | 58 MiB | 4.5 GiB |

What the run left: packages.added: aardvark-dns, acl, buildah, catatonit, conmon, containers-storage, cpp, cpp-15, cpp-15-x86-64-linux-gnu, cpp-x86-64-linux-gnu, criu, crun, dns-root-data, dnsmasq-base, fuse-overlayfs, gcc-15-base, golang-github-containers-common, golang-github-containers-image, libcompel1, libcriu2, libisl23, libmpc3, libnet9, libprotobuf-c1, libslirp0, libsubid5, libyajl2, netavark, passt, podman, porelo, porelo-adapter-forgejo, porelo-agent-agy, porelo-agent-claude, porelo-agent-codex, porelo-agent-omp, porelo-agent-pi, porelo-matrix-homeserver, porelo-message-sluice-filter, porelo-message-transport-matrix, python3-protobuf, python3-pycriu, slirp4netns, uidmap; units.added: netavark-dhcp-proxy.service, netavark-dhcp-proxy.socket, netavark-firewalld-reload.service, podman-auto-update.service, podman-auto-update.timer, podman-clean-transient.service, podman-kube@.service, podman-restart.service, podman-user-wait-network-online.service, podman.service, podman.socket, porelo-host-firewall.service, porelo-host-task-sweep.service, porelo-host-task-sweep.timer, porelo-matrix-homeserver.service, porelod.service; accounts.added: dnsmasq; directories.added: /var/lib/fwupd.

Not measured: agent, job, task.

<!-- measures:end -->
