# Role `vm_pool`

The host's VM pool: one small VM per run account, made from each system's cloud image by its pinned digest, that
`porelo-machines acceptance --pool` rents from through the pool file `/etc/porelo-host/pool/pool.json`
(porelo-buildtools' `porelo-machines-pool/1`), readable by any job user and holding nothing secret. It runs where the
host setting `porelo_host_vm_pool` asks for it, after the forge; the run key stays on the host (`root:root`, `0600`)
and reaches jobs only as the forge organization's Actions secret `PORELO_POOL_SSH`. At `down`, the secret and the VMs
with their snapshots and keys are deleted.

A run account gives itself back with `sudo porelo-pool-give-back`, the one command that takes no argument: its VM
powers off, and `porelo-pool-revert` on the host, outside every job, reverts it to the base snapshot taken live with
the account ready, so nothing a run did - as root through the package manager too - reaches the next. The VMs are
made by `files/porelo-vm`, the same code `build/molecule.sh` makes the collection's test VM with.
