# HO04 — The Host's Base: Packages, KVM, Podman

**Status:** Estimated.
**Size:** S - one role with its tests, no contract another repository reads.

**What must be true.** After `up`, the host has the packages the project needs, KVM usable by Porelo's account
(`/dev/kvm` and libvirt), and podman for that account, rootless; a second run changes nothing.

## Plan

- **One role, `base`**: `install.yml` (the packages, from a list in `defaults/main.yml`, `base_packages`, through
  `ansible.builtin.package`), `kvm.yml` (the CPU's virtualization checked first and the run stopped with the reason
  if it has none; libvirt enabled; the account in the `kvm` and `libvirt` groups), `podman.yml` (podman, the
  account's `subuid`/`subgid` ranges, lingering enabled so its user units run without a login).
- **The account is a variable** (`base_account`), from the inventory Porelo writes; the role makes no account itself,
  that is [HO02](README.md#ho02)'s.
- **Platform files** by the `first_found` pattern, with only `Ubuntu-26.yml` at first, so another system is a file
  and not a change of the tasks.
- **`meta/argument_specs.yml`** for every variable, and the README with its idempotency and check-mode statement.
- **Red first**: `verify.yml` asserting `/dev/kvm` is usable by the account, run against the role without the group
  task, fails; then green.

## Acceptance

- On [HO03](README.md#ho03)'s VM: the account can start a podman container and open `/dev/kvm`; `idempotence`
  reports `changed=0`.
- On a machine without virtualization, the role stops with a message naming what is missing, before it installs
  anything.
