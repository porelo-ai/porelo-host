# The host playbook

Brings a Porelo project up on a server and takes it down again, owned or rented by the hour: the Ansible collection
`porelo.host`, run on the host itself with `-c local` and the [JSON line callback](lines.md) `porelo.host.lines`.

**`porelo.host.up`, in two plays around the person's step.** The first play runs `base` (packages, KVM with libvirt,
podman), `porelo`'s install and setup script (which makes Porelo's account with linger and subordinate ids), `base`'s
account part (the account in `kvm` and `libvirt`, and the person's ssh key on the account for the stop), `drive` (the
`noexec` folder, and the drive's client syncing the person's folder when logged in: Tresorit's, the one provider
implemented today), and `porelo setup` with `porelo vault status`, and `vpn`'s needs part (whether the host's VPN key is
there). Each role that needs the person's step adds what is missing (`drive`, `vault-new` with `keys`, `vault`, or
`wireguard`) to `porelo_host_needs`. The second play stops first with a [waiting line](lines.md) while
`porelo_host_needs` is not empty; the person's stop gives every need but the drive's login on [standard
input](lines.md), from their secrets file on the desktop. Once the drive is synced and the vault is open, it runs `vpn`
(WireGuard with the host's key, which the stop wrote into `/etc/wireguard`, read by `wg` itself, and nftables leaving
only ssh and the VPN on the public interfaces), `porelo`'s project part (each key of the machine file checked in the
vault, where the stop put it, `project follow --signed-by`), `forge` and `vm_pool` where the host settings ask for them,
and `porelo`'s agents part (every offered agent and the project's transport packages installed, with no task started or
stop for a sign-in). A second `up` runs both plays from the top and changes only what differs, read from the commands'
own exit codes and `--json` output, so resuming is idempotence, with no marker file of the playbook's own.

The [local forge](local-forge.md) connects task branches and independent builds to the person's merge and gathered-push
decisions.

Where the host runs a forge, `~/.config/porelo/ca-certificates.pem` of Porelo's account keeps the forge's CA in a
marked block beside the person's certificates, and `~/.config/porelo/task-ca-certificates.pem` holds that CA alone;
both are mode `0600` in the account's `0700` Porelo configuration directory. `down` removes the marked block and the
task CA file, and removes the account's CA bundle if only whitespace remains.

Forgejo is bounded to 2 CPUs of time, 2 GiB of memory and 1024 processes and threads; its runner daemon to 1 CPU,
512 MiB and 256. The runner takes 4 jobs at once, and each gets 4 CPUs of time, 8 GiB and 2048 processes and threads,
with `OMP_NUM_THREADS=4` to tell tools its core count; these are fixed role defaults, independent of the host's size.
Before writing the runner's configuration, `up` refuses jobs that, with the VM pool, would take more than half the
host: capacity × CPUs per job above half the processors, or capacity × memory per job plus the pool's memory above
half of `MemTotal`, naming both sides.
`up` refuses Porelo's account, and the forge's two accounts where it runs, if their user managers lack any of
`cpu`, `memory` and `pids`, naming the account and every missing controller. Before changing libvirt or making VMs,
it also refuses a pool whose memory (systems × accounts per system × memory per VM) exceeds half of `MemTotal`,
naming the pool's memory and the host's total memory.

**`porelo.host.down`, the other way round.** Takes the VM pool and the forge off the host, stops every running task
of the account with `porelo task stop --all` and clears
the vault (`porelo vault clear --yes`), stops the VPN, waits for the drive to finish syncing before logging the client
out with `--unlink` and unmounting the folder, and takes the person's ssh key off the account last. Every step takes
down only what is there, so `down` after a failed `up` works too.
