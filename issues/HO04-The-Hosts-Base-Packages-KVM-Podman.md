# HO04 — The Host's Base: Packages, KVM, Podman

**Status:** Implementing.
**Size:** S - one role with its tests, no contract another repository reads.

**What must be true.** After `up`, the host has the packages the project needs, KVM usable by Porelo's account
(`/dev/kvm` and libvirt), and podman for that account, rootless; a second run changes nothing.

## Plan

- **One role, `base`**, in two entry points, changed from the plan's `podman.yml` once Porelo's own setup script was
  read: that script makes the account, with its linger and its subuid and subgid ranges, so the role makes none of
  them.
  - **`main`**, machine-wide: `cpu.yml` (the CPU's `vmx` or `svm` read first, and the run stopped with the reason
    before anything is installed), `install.yml` (`base_packages` and KVM's and podman's packages by
    `ansible.builtin.apt`), `kvm.yml` (libvirt started and enabled).
  - **`tasks_from: account`**, run once Porelo's script made the account: it stops if the account is missing, adds it
    to `kvm` and `libvirt`, and stops if its linger or its subordinate ids are missing, naming which.
- **The account is a variable**, `base_account`, from the collection-wide `porelo_host_account` the inventory carries.
- **Platform files** by the `first_found` pattern, only `Ubuntu-26.yml` so far; the role reads the minimal facts
  itself where the play gathered none.
- **`meta/argument_specs.yml`** for both entry points, and the role's README.
- **In the scenario**, until Porelo's script runs there, the converge stands in for it: it makes `porelo-test` and
  its linger as the script does, and writes the inventory `host up` writes.

## Acceptance

- [x] On [HO03](README.md#ho03)'s VM, as the account: KVM answers `KVM_GET_API_VERSION` through `/dev/kvm`, `virsh -c
  qemu:///system` lists domains, and `podman unshare` maps more than the account's own id; `idempotence` reports
  `changed=0`. A container was not started: that needs an image from the network, which the test does not pull.
- [x] Seen red: the account left out of the groups could not open `/dev/kvm`; on a CPU with `svm` and `vmx` off the
  role stopped with "offers no virtualization … nothing was installed", and its install task never ran; an account
  without linger made the account part stop, naming it.
