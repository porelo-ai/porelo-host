# HO12 — The VM Pool

**Status:** Backlog; its acceptance blocked by porelo-buildtools
[BT24](https://github.com/porelo-ai/porelo-buildtools/blob/main/issues/README.md#bt24).
**Size:** L - one role here, but the pool is `porelo-machines`' to rent from, so what the role makes is a contract
with porelo-buildtools, and its VMs need nested KVM on the host.

**What must be true.** Where the project names machine kinds for its tests, the host carries VMs with run accounts
that `porelo-machines` rents from, each reset when given back, and the pool's size is the host's limit; `down`
deletes them with nothing left.

## Plan

- **One role, `vm_pool`**, run only when the inventory names machine kinds: `image.yml` (each system's cloud image,
  its digest checked against the one the distribution publishes), `vms.yml` (one VM per system by libvirt, a
  copy-on-write disk, a cloud-init seed with a key made on the host), `accounts.yml` (the run accounts in each VM, four
  to start with, and `porelo-reset-account` and `porelo-pool-reset` installed there), `machines.yml` (the pool
  file `porelo-machines` reads, `porelo-machines-pool/1`: per VM its `os`, address, host key and run
  accounts, and the pool's admin account and key, readable by the Forgejo runner's account alone).
- **A reset makes the account anew**, as the operator decided: `porelo-pool-reset <account>`, run by the admin with
  sudo, runs `porelo-reset-account` as the account, stops its processes, removes its containers, then `userdel -r`,
  `useradd` and the run key again. Packages a run installed with sudo stay, the accepted risk written in
  `doc/decisions.md`. `porelo-reset-account` comes into the collection, so it lives in a repository.
- **Made the same way as the test VM `build/molecule.sh` makes**, by one task file both use, so the pool and the test
  are made by the same code.
- **Names say the project and the host's run**, so `down` deletes exactly what this host's `up` made, by name, and
  refuses a domain it cannot attribute.
- **Red first**: `verify.yml` rents an account through `porelo-machines`, gives it back, and asserts it is reset; it
  fails without `porelo-reset-account`.

## Measured

- **Nested KVM one level below the Molecule VM works**, on this machine: the VM `build/molecule.sh` makes, with
  `--cpu host-passthrough`, has `/dev/kvm`, and a guest inside it boots its kernel to the initramfs with `-accel kvm`
  in 7.3 s, against 12.4 s emulated (`tcg`); the VM removed after.

## Acceptance

- On the test VM `build/molecule.sh` makes, with nested KVM: `porelo-machines` rents and returns a pool account, and
  an acceptance leg runs in it.
- After `down`, `virsh list --all` and the storage pool show nothing of the run.

## To be checked

- Nested KVM three levels deep, on GitHub's runner: the Molecule VM inside the runner's VM, and a pool VM inside
  that; measured locally only two levels deep so far.
