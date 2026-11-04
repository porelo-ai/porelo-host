# HO118 — KVM Only On A Host That Asks

**Status:** Review.

**What must be true.** A host's installation asks for KVM by one setting, off by default. Only a host that says yes has its
CPU checked for `vmx` or `svm` and gets KVM and libvirt; any other host comes up on a CPU without them.

## Why

`base` stops every host without `vmx` or `svm`, before anything is installed, so an ordinary cloud server cannot be a host.
That follows from this collection's own development, where a job may drive a VM, and from the VM pool; the operator decided
it is no general need. Read on `main`:

| What uses KVM or libvirt | Who for | With no |
| --- | --- | --- |
| `base`: `cpu.yml`, three packages in `install.yml`, `kvm.yml` | everything below | skipped |
| `forge`'s `runner.yml`: `porelo-runner` in `kvm` | a job that drives a VM | not in the group; the task names a group that may not exist |
| `vm_pool`: `virsh`, `virt-install`, its VMs | jobs that rent from the pool | a pool cannot be asked for |
| `porelo-host-person`: a person in `kvm` and `libvirt` | a person who drives VMs | already only where the groups exist |

A task, the gate, the forge's own server and the homeserver use none of it. `base`'s `tasks_from: account`, which would put
Porelo's account in both groups, has no caller on `main`, though `doc/index.md` says it runs.

## What a job loses with no

`/dev/kvm` and the pool, so a job that makes a VM and a job that rents a pool account: this collection's own Molecule in a
forge's build is such a job, and a host that runs it says yes. A job in a container loses nothing.

## Plan

- **The setting:** `porelo_host_kvm`, a boolean in the inventory beside `porelo_host_forge`, default `false`. Optional, so the
  inventory's version stays.
- **`base`:** `cpu.yml`, KVM's packages and `kvm.yml` only with it. No removal on a host that has them: a later `up` with no
  leaves what stands, and says nothing new.
- **`forge`:** `porelo-runner` in `kvm` only with it.
- **`up`:** `porelo_host_vm_pool` without `porelo_host_kvm` stops in the first play, before anything is installed, naming both.
- **Remove** `tasks_from: account`, unused, and correct `doc/index.md`, `README.md`, the roles' READMEs and `doc/decisions.md`.
- **The interface writes the setting;** the words in its dialog and for a refused CPU are its own.

## Acceptance

- Unit, `test_base_cpu.py` with the real `ansible-playbook`: no setting on a CPU without the flags passes; yes stops with the
  same message; yes on a CPU with them passes.
- Molecule, a run with the setting off on a VM whose CPU has `vmx` and `svm` disabled: `up` and `down` pass, `idempotence`
  reports no change, no `qemu-system-x86` or `libvirt-daemon-system`, `porelo-runner` not in `kvm`, a person admitted and purged.
  A second CI leg, about as long as the first.
- Molecule, the run with the pool stays as it is with the setting on: KVM answers through `/dev/kvm`.
- A pool asked for with no setting stops before an `apt` task, in a unit test.

## What a run showed

`build/molecule.sh` with `PORELO_HOST_MOLECULE_KVM=off`, forge on, on a VM with `vmx` and `svm` disabled by `PORELO_VM_CPU`: `/dev/kvm` absent, the
flags empty, all stages green, none of KVM's packages, `porelo-runner` not in `kvm`, a person admitted and purged. The test found one fault:
the setting's own stop failed on an undefined value. A person admitted and `down` run with no `virsh`.

## Not covered

- **That an ordinary cloud server carries the rest.** On a `cx33` the first run stopped at this check, so nothing after it has
  run on one. How many tasks fit on 8 GB is not measured either.
- **Who may use `libvirt` on a yes host.** Every person admitted gets the group, as today.
