# HO03 — Molecule Tests On A Throwaway VM

**Status:** Implementing.
**Size:** M - one Molecule scenario and the script that makes and deletes its VM, an acceptance step every role is
tested by; no contract another repository reads.

**What must be true.** Every role, and `up` and `down` together, are tested on a fresh Ubuntu 26.04 machine made for
the run and deleted after it, with KVM inside it as on a rented host. The test proves a second run changes nothing,
and leaves nothing behind on this machine, after a failure too.

## Plan

- **Why not a container**: the roles install packages, KVM, podman and systemd units and mount a drive. A container
  shows none of that truly, and the shared VMs are other agents' test machines, where a playbook that installs as
  root changes what their runs measure.
- **Decided**: Molecule makes and deletes its own libvirt VM per run, 4 vCPUs and 4 GB, here before every hand-over
  and in the Build. Measured first by a hand-started probe: GitHub's `ubuntu-24.04` runner offers KVM, and the
  scenario ran green there; so the Build's `molecule` job runs it on `main` and on the project's own pull requests,
  never on a fork's, with libvirt, qemu-img, dnsmasq, virt-install and xorriso pinned by version.
- **The VM is the script's, not Molecule's**, changed from the plan's `create.yml` and `destroy.yml`: Molecule runs in
  the pinned image, which reaches neither `virsh` nor this machine's libvirt. `build/molecule.sh` makes the VM through
  `qemu:///system`, pool `images`, network `default`: a 20 G copy-on-write disk over the Ubuntu 26.04 cloud image
  `build/test-image` pins by URL and SHA-256 (checked against Ubuntu's `SHA256SUMS`, downloaded once into
  `~/.porelo/cache/`, uploaded once as the base volume `porelo-host-base-<digest>.qcow2`), a cloud-init seed with a
  client key and a host key made for the run and accepted alone, `host-passthrough` for nested KVM, 4 vCPUs and 4 GB.
  Everything a run makes is named `porelo-host-molecule-<run>`.
- **What it leaves**: it refuses to start while anything named `porelo-host-molecule-*` is in libvirt, naming it; at
  its end, after a failure and on an interrupt too, it stops the domain before it undefines it, deletes the disk and
  the seed, and believes that only when libvirt lists none of them, else it names what is left and exits 1. It reads
  `virsh` with `LC_ALL=C`. cloud-init is waited for once, and anything but a clean finish fails at once.
- **`extensions/molecule/default/`**, ansible-native as the `ansible-new-molecule` skill sets out: `molecule.yml`
  with no `driver:`, `platforms:`, `provisioner:` or `verifier:` blocks, the inventory from the script, and the
  sequence `syntax`, `converge`, `idempotence`, `verify`.
- **`converge.yml`** does what `host up` does: installs Ubuntu's own `ansible-core`, copies the collection's tarball
  into the VM and installs it, and runs `porelo.host.up` with `-c local`, so the test runs the version a host runs,
  not the image's. **`verify.yml`** asserts what a host has after `up`: the collection in the version under test,
  `ansible-core` from Ubuntu, and KVM answering `KVM_GET_API_VERSION` through `/dev/kvm`. Each role's issue adds what
  its role promises; the `down` scenario comes with [HO09](README.md#ho09)'s `down.yml`.
- **`playbooks/up.yml`** is a play on `localhost` with no role yet, so the scenario has something to run.

## Acceptance

- [x] `build/molecule.sh` passes: `syntax`, `converge`, `idempotence` with `changed=0`, `verify`; libvirt lists
  nothing of the run afterwards.
- [x] Seen red: `verify` refused a version other than the one under test, naming both; and a VM with `svm` and `vmx`
  switched off, where KVM did not answer. A first `verify` that only looked for `/dev/kvm` passed on such a VM,
  since Ubuntu makes the node anyway; it was replaced. A converge that skipped installing the collection failed.
- [x] Seen red: a clean-up with the domain's stop broken on purpose named the domain left and exited 1; a run
  interrupted in `converge` exited 130 and left nothing; a planted volume named like a run made the script refuse to
  start, naming it.
- [x] The time of one full run is in `doc/`: about a minute with the image cached.
- [x] The probe on GitHub's runner, run 39145070246: the VM up after 17 s, the scenario green, in about three minutes.
  Its three runs before failed in the probe's own setup, never on KVM: no `qemu-img`, the network not started, and
  rootless podman under `sg`.
- [ ] The Build's `molecule` job green on GitHub.
