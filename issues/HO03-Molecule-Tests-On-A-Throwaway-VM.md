# HO03 — Molecule Tests On A Throwaway VM

**Status:** Backlog.
**Size:** M - one Molecule scenario with its own create and destroy, an acceptance step every role is tested by; no
contract another repository reads.

**What must be true.** Every role, and `up` and `down` together, are tested on a fresh Ubuntu 26.04 machine made for
the run and deleted after it, with KVM inside it as on a rented host. The test proves a second run changes nothing,
and leaves nothing behind on this machine, after a failure too.

## Plan

- **Why not a container**: the roles install packages, KVM, podman and systemd units and mount a drive. A container
  shows none of that truly, and the shared VMs are other agents' test machines, where a playbook that installs as
  root changes what their runs measure.
- **Decided**: Molecule makes and deletes its own libvirt VM on this machine per run, 4 vCPUs and 4 GB; it runs here
  before every hand-over, and the GitHub Build runs the linters and the tarball only.
- **`extensions/molecule/default/`**, ansible-native as the `ansible-new-molecule` skill sets out: `molecule.yml`
  with no `driver:`, `platforms:`, `provisioner:` or `verifier:` blocks, and the full default sequence including
  `idempotence`.
- **`create.yml`** makes one VM through libvirt on this machine: a copy-on-write disk over the Ubuntu 26.04 cloud
  image (downloaded once, its digest checked against the one Ubuntu publishes), a cloud-init seed with an ssh key made
  for the run, nested KVM, 4 vCPUs and 4 GB. The VM's name says the agent and the run
  (`porelo-host-molecule-<run>`), and the run's id goes into a file in Molecule's ephemeral directory.
- **`destroy.yml`** removes exactly that VM, its disk and its seed by the recorded name, refuses a name it did not
  make, and runs on an interrupt too; `create.yml` refuses to start over a VM of an earlier run that is still there,
  naming it.
- **`converge.yml`** does what `host up` does: copies the collection's tarball into the VM, installs Ubuntu's own
  `ansible-core` there and runs `playbooks/up.yml` with `-c local`, so the test runs the version a host runs, not the
  image's; **`verify.yml`** asserts what `up` promises (packages, `/dev/kvm`,
  podman, the account, `porelo doctor`); a second scenario, `down`, runs `up`, then `down`, and asserts what `down`
  leaves.
- **Red first**: `verify.yml` against a converge that skips the KVM role must fail on `/dev/kvm`; a `destroy.yml` run
  after a planted failure in `converge` must still leave no domain and no volume of the run.

## Acceptance

- `molecule test` passes, and `idempotence` reports `changed=0`.
- After it, and after a run interrupted in `converge`, `virsh list --all` and `virsh vol-list images` show nothing
  named for the run.
- The time of one full run is measured and written in `doc/`, so a hand-over can say how long it takes.

## To be checked

- Whether `qemu:///system` is reachable through `sg libvirt` from Molecule's playbooks, and in which storage pool the
  run's volumes belong (`images` exists).
- How long the Ubuntu 26.04 cloud image takes to boot with cloud-init here, measured, before the first long run.
