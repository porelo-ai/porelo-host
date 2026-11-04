# Measured machines

A result file describes one disposable machine, and each table below is made from one. **Nothing here is a recommendation yet.**

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

**What these do not say.** They are idle numbers on local VMs, with 4 CPUs and a 20 GiB virtual disk: they show memory and disk, not a real host's time. They do not
read what an `up` itself takes while it runs, and a job or a task needs more on top: tasks, agents and jobs are "not measured", as each table says, so a size
that has to hold work does not rest on them.

<!-- measures:start -->

### local-vm-16g

local local-vm-16g: 4 CPUs of AMD Ryzen AI 7 PRO 350 w/ Radeon 860M, 15988 MiB, ubuntu 26.04, KVM True; collection 0.5.11-snapshot, from snapshots.

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

local local-vm-4g: 4 CPUs of AMD Ryzen AI 7 PRO 350 w/ Radeon 860M, 3910 MiB, ubuntu 26.04, KVM True; collection 0.5.11-snapshot, from snapshots.

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

local local-vm-8g: 4 CPUs of AMD Ryzen AI 7 PRO 350 w/ Radeon 860M, 7936 MiB, ubuntu 26.04, KVM True; collection 0.5.11-snapshot, from snapshots.

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
