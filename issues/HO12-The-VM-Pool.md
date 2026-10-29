# HO12 — The VM Pool

**Status:** Review.
**Size:** L - one role here, but the pool is `porelo-machines`' to rent from, so what the role makes is a contract
with porelo-buildtools, and its VMs need nested KVM on the host.

**What must be true.** Where the project names machine kinds for its tests, the host carries VMs with run accounts
that `porelo-machines` rents from, each reset when given back, and the pool's size is the host's limit; `down`
deletes them with nothing left.

## Plan

- **One role, `vm_pool`**, run in `up`'s second play after the forge where the host setting `porelo_host_vm_pool` is
  set (`systems` from `ubuntu` and `fedora`, `accounts` 1 to 8), requiring the forge: each system's cloud image fetched
  by its pinned SHA-256 and checked against the digest list the distribution publishes; one small VM per run account
  (`1536` MiB, `1` vCPU by default) on a copy-on-write disk over the image's base volume, each holding one account
  `run`, a host key per VM and one run key made on the host (`root:root`, `0600`, in `/var/lib/porelo-host/pool` and
  sent into the forge organization's Actions secret `PORELO_POOL_SSH`, never mounted as a file; the VM's host key going
  into its cloud-init seed by the shell, never through an Ansible variable), and its base snapshot taken live once `run`
  says `ready` in `/var/lib/porelo-pool/run`; and the pool file `/etc/porelo-host/pool/pool.json`
  (`porelo-machines-pool/1`: per VM its `name`, `os`, `address`, `hostKey` and `accounts` `["run"]`, no key), mode
  `0644` in `/etc/porelo-host/pool` (`0755`), mounted read-only into the runner's jobs.
- **Every run starts on a clean machine, reverted to its base snapshot**: since a run account is root on its VM through
  the package manager, an account reset in place would leave what a run changed as root. The run account gives itself
  back with `sudo -n porelo-pool-give-back` (no argument): the VM writes `resetting` and powers off, and
  `porelo-pool-revert`, a systemd service on the host outside every job, sees it stopped and reverts it to its base
  snapshot, which says `ready` again.
- **Made the same way as the test VM `build/molecule.sh` makes**, by `roles/vm_pool/files/porelo-vm` (`base`, `seed`,
  `make`, `address`, `delete`), which both use, so the pool and the test are made by the same code.
- **Names say what they are**, `porelo-pool-<system>-<n>`, so `down` deletes exactly the pool's VMs by that name and
  touches no other domain; the revert reads its list of VMs from the role and touches no other either.
- **Red first**: `verify.yml` leaves files in the run account's home and as root in `/etc`, gives the account back, and
  asserts the VM comes back `ready` and clean; it fails with the revert broken.

## Measured

- **Nested KVM one level below the Molecule VM works**, on this machine: the VM `build/molecule.sh` makes, with
  `--cpu host-passthrough`, has `/dev/kvm`, and a guest inside it boots its kernel to the initramfs with `-accel kvm`
  in 7.3 s, against 12.4 s emulated (`tcg`); the VM removed after.

## Built

- The role `porelo.host.vm_pool`, run in `up`'s second play after the forge where `porelo_host_vm_pool` is set
  (`{systems: [ubuntu, fedora], accounts: 1-8}`), requiring the forge.
- One small VM per run account (`1536` MiB, `1` vCPU by default), each holding one account `run`, made by
  `roles/vm_pool/files/porelo-vm` (`base`, `seed`, `make`, `address`, `delete`), which `build/molecule.sh` now also
  uses for its test VM.
- Each system's cloud image fetched by its pinned SHA-256 and checked against the digest list its distribution
  publishes (Ubuntu 26.04 `release-20260927`, Fedora Cloud `44-1.7` Generic).
- A host key per VM and one run key made on the host (`root:root`, `0600`, in `/var/lib/porelo-host/pool/run-key`); the
  run key reaches jobs only as the forge organization's Actions secret `PORELO_POOL_SSH`, the VM's host key goes into
  its cloud-init seed by the shell, never through an Ansible variable, and each VM's base snapshot is taken live once
  its `run` account says `ready` in `/var/lib/porelo-pool/run`.
- `porelo-pool-give-back` in each VM and `porelo-pool-revert` (`porelo-pool-revert.service`) on the host outside every
  job: the run account gives itself back with `sudo -n porelo-pool-give-back` (no argument), the VM writes `resetting`
  and powers off, and the host reverts the stopped VM to its base snapshot, which says `ready` again.
- The pool file `/etc/porelo-host/pool/pool.json` in `porelo-buildtools`' format `porelo-machines-pool/1` (per VM its
  `name`, `os`, `address`, `hostKey` and `accounts` `["run"]`, no key), mode `0644` with `/etc/porelo-host/pool`
  (`0755`) mounted read-only into the forge runner's jobs; `down` deletes the secret `PORELO_POOL_SSH`, the pool VMs
  with their snapshots, disks and seeds by name, and the pool's keys and file, before the forge, while the images and
  their base volumes stay as a cache named by digest.
- **Molecule**, green, 5 of 5 stages, on this machine, 2026-10-22 15:20Z-15:39Z, on the commit that adds the role, with
  one Ubuntu pool VM of 1024 MiB nested in the test VM (now 6144 MiB). The pool file names one VM with one account and
  no key, mode `0644` `root`; the run key is `root`'s, mode `0600`, in `/var/lib/porelo-host/pool`. A workflow job of
  the forge (its image running as its own user) reads the pool file and gets the run key from the organization's Actions
  secret `PORELO_POOL_SSH`, and the digest it publishes equals the host key's. The `-vvv` output of a whole `up` is
  searched for every body line of the pool's run key and a VM's private host key, the keys reaching `grep` only on a
  pipe and never in a register. A half-made VM's volumes are deleted before it is made again, and a failure of a task
  that hides its output for a secret still says why. After a run left a file in the account's home and one written as
  root into `/etc`, a give-back brought the VM back `ready` with both gone; the revert ran once, watching, never started
  again. After the two `down`s of the test (the first stopping at the unsynced drive), the forge's Actions secret
  `PORELO_POOL_SSH` was deleted exactly once, and no pool VM, volume, seed, key, directory or unit is left.
- **Molecule**, green, 5 of 5 stages, on this machine, 2026-10-25 09:31Z-09:50Z, 18.4 min, with `porelo-machines` built
  from porelo-buildtools `3bf62cf` (the commit that provisions a pool
  lease as root through `sudo -n`) and handed over by a SHA-256 manifest checked on the host and again on the test VM:
  - a renter that returned its lease normally, and one killed with SIGKILL while holding it, each left a file in the
    run account's home and one written as root in `/etc`; the next rental of the same VM and account found neither;
  - `porelo-machines acceptance --pool /etc/porelo-host/pool/pool.json` installed published Porelo, made its
    unprivileged `acceptance` account and ran a leg in it; the next rental found that account gone;
  - after `down`, the libvirt listings (read first, so a failed query cannot pass as empty) showed no pool VM or
    volume, and the test VM, its disk and its seed were gone.
- **Seen red first**, each break restored, 2026-10-22 14:53Z-15:39Z, in runs with faults put in: a line of the run key
  in the `-vvv` output (the check named only the key file, never the key), and `down` deleting another secret name (both
  `down`s reported unchanged). Earlier red runs caught the job's digest of the secret against the host's key (the forge
  given the public key) and `down` leaving a VM's directory; a job that could not read the pool file under rootless
  podman when it was `0640` for the runner's group; the VM never coming back `ready` with the revert taking no snapshot;
  and `virsh event --all --event lifecycle`, which virsh refuses at once, starting the revert again 83 times. That last
  fault was in the first green run too, hidden by the revert's first loop; the check on its restarts now finds it.
  2026-10-25 09:51Z-10:08Z, with `porelo-machines` built without the reset of an account a killed renter left dirty,
  the normal return stayed clean and the rental after the SIGKILL found both files, failing the check; the break was in
  a copy of the source only.

## Acceptance

- On the test VM `build/molecule.sh` makes, with nested KVM: `porelo-machines` rents and returns a pool account, and
  an acceptance leg runs in it.
- After `down`, `virsh list --all` and the storage pool show nothing of the run.

## To be checked

- On GitHub's runner (AMD, nested KVM present) the pool VM gets its address but does not say ready within 15 minutes
  (porelo-host Builds 16 and 17, 2026-10-22); the Build leaves the pool out (`PORELO_HOST_MOLECULE_POOL=off`) until that
  is found; local Molecule runs it.
