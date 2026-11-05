# Role `vm_pool`

The host's VM pool: one small VM per run account, made from each system's cloud image by its pinned digest, that
`porelo-machines acceptance --pool` rents from through the pool file `/etc/porelo-host/pool/pool.json`
(porelo-buildtools' `porelo-machines-pool/1`), readable by any job user and holding nothing secret. It runs where the
host setting `porelo_host_vm_pool` asks for it, on a host with `porelo_host_kvm` true, after the forge; the run key stays on the host (`root:root`, `0600`)
and reaches jobs only as the Actions secret `PORELO_POOL_SSH` of each project's organization, sent by
`porelo-host-project pool-key send` on the forge account's socket; a project added later gets it from its own `add`. At
`down`, `pool-key withdraw` takes that secret from every project, and the VMs with their snapshots and keys are deleted.

Before changing libvirt or making VMs, the role checks that the total memory for every system and account fits in
half of the host's `MemTotal`; the refusal names both amounts. The `memory` entry point runs this check alone with
`vm_pool_systems`, `vm_pool_accounts` and `vm_pool_memory` (MiB per VM).

A run account gives itself back with `sudo porelo-pool-give-back`, the one command that takes no argument: its VM
powers off, and `porelo-pool-revert` on the host, outside every job, reverts it to the base snapshot taken live with
the account ready, so nothing a run did - as root through the package manager too - reaches the next. A revert brings
back the snapshot's clock, so the VM's network link stays down until the guest agent has set it from the host's; a VM
whose clock cannot be set stays off and says so, until the service restarts or `up` runs, and `up` refuses a VM made
before its guest agent was added, naming `down` and `up`. The VMs are made by `files/porelo-vm`, the same code `build/molecule.sh` makes the collection's test VM with.
