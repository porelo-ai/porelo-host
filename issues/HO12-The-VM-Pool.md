# HO12 — The VM Pool

**Status:** Backlog.
**Size:** L - one role here, but the pool is `porelo-machines`' to rent from, so what the role makes is a contract
with porelo-buildtools, and its VMs need nested KVM on the host.

**What must be true.** Where the project names machine kinds for its tests, the host carries VMs with run accounts
that `porelo-machines` rents from, each reset when given back, and the pool's size is the host's limit; `down`
deletes them with nothing left.

## Plan

- **One role, `vm_pool`**, run only when the inventory names machine kinds: `image.yml` (each system's cloud image,
  its digest checked against the one the distribution publishes), `vms.yml` (one VM per system by libvirt, a
  copy-on-write disk, a cloud-init seed with a key made on the host), `accounts.yml` (the run accounts in each VM, four
  to start with, and `porelo-reset-account` installed there), `machines.yml` (the file `porelo-machines` reads to
  find the pool's VMs and accounts).
- **Made the same way as the test VM `build/molecule.sh` makes**, by one task file both use, so the pool and the test
  are made by the same code.
- **Names say the project and the host's run**, so `down` deletes exactly what this host's `up` made, by name, and
  refuses a domain it cannot attribute.
- **Red first**: `verify.yml` rents an account through `porelo-machines`, gives it back, and asserts it is reset; it
  fails without `porelo-reset-account`.

## Acceptance

- On the test VM `build/molecule.sh` makes, with nested KVM: `porelo-machines` rents and returns a pool account, and an acceptance leg runs in
  it.
- After `down`, `virsh list --all` and the storage pool show nothing of the run.

## To be checked

- With Agent Core: which file `porelo-machines`' `LocalVms` reads for its VMs and accounts, and its version, so it
  becomes the contract this role writes; [PJ22](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj22) keeps the pool `porelo-machines`'.
- Nested KVM inside the test VM `build/molecule.sh` makes, three levels deep, measured before the first run; if it is too slow, the pool is
  tested on a rented host only.
