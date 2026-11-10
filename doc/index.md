# The host playbook

Brings a Porelo project up on a server and takes it down again, owned or rented by the hour: the Ansible collection
`porelo.host`, run on the host itself with `-c local` and the [JSON line callback](lines.md) `porelo.host.lines`.

[Which server for what](machines.md) records disposable measuring runs and keeps missing readings explicit.

**`porelo.host.up`, in two plays around the person's step.** The first play asks `check`, one read-only look at the machine reporting everything it lacks at once, then runs `base` (packages, KVM with libvirt only where `porelo_host_kvm` asks for it,
podman, the SSH policy and a firewall allowing only port 22 on public interfaces), `porelo`'s install (which makes Porelo's account with linger and subordinate ids), `porelo setup`
with `porelo vault status`, and, where the host runs a forge,
`forge`'s request part (whether a certificate signed by the person's CA holds for it). Each role that needs the person's
step adds what is missing (`vault-new` with `keys`, or `vault`) to `porelo_host_needs`.
The second play stops first with a [waiting line](lines.md) while `porelo_host_needs` is not empty; the person's stop
gives every need on [standard input](lines.md), from their secrets file on the desktop. Once the vault is open, it runs
`porelo`'s project part (the machine file read from
`/etc/porelo-host/setup/`, where the interface uploaded it, each key of the machine file checked in the vault, where the
stop put it), `forge` and `vm_pool` where the host settings ask for them, and `porelo`'s
agents part (every offered agent and the project's transport packages installed, with no task started or stop for a
sign-in). A second `up` runs both plays from the top and changes only what differs, read from the commands' own exit
codes and `--json` output, so resuming is idempotence, with no marker file of the playbook's own.

A host's `.local` name does not answer after `up`, as the firewall opens no port for it; use a DNS name or a name entry of your own.

The [local forge](local-forge.md) connects task branches and independent builds to the person's merge and gathered-push
decisions.

The shared [Matrix homeserver](matrix.md) accepts clients through the Matrix transport's Unix socket gate. Admission needs no host
registration token.

Forgejo is bounded to 2 CPUs of time, 2 GiB of memory and 1024 processes and threads; its runner daemon to 1 CPU,
512 MiB and 256. The runner's unset job count, CPU and memory bounds fit the host's share for work beside the VM pool,
`porelo_host_work_share` percent of it, 1 to 100 and unset 50,
as the forge role's README says. Each job gets 2048 processes and threads,
with `OMP_NUM_THREADS` defaulting to its CPU quota.
Before writing the runner's configuration, `up` refuses jobs that, with the VM pool, would take more than that share:
capacity × CPUs per job above its part of the processors, or capacity × memory per job plus the pool's memory above
its part of `MemTotal`, naming both sides and the setting. Set above 50, `up` writes a note that the host's own work
keeps less than half; set outside 1 to 100, the check refuses it before anything is installed.
`up` refuses Porelo's account, and the forge's two accounts where it runs, if their user managers lack any of
`cpu`, `memory` and `pids`, naming the account and every missing controller. Before changing libvirt or making VMs,
it also refuses a pool whose memory (systems × accounts per system × memory per VM) exceeds that share of `MemTotal`,
naming the pool's memory and the host's total memory.

**`porelo.host.down`, the other way round.** Pauses the follow timer and service before its checks, resuming the
timer on refusal. Refuses while any project's `main` on the host's forge is not known to be at its central forge,
asked afresh with `porelo-host-project give-back-check`: `ahead`, `moved-on` or `cannot-say`, naming each repository;
a row the project file gives no central address has no copy there to hold it, and a project whose first repository is
not yet on the forge has none either. `porelo-host down --give-back-anyway` gives the host back
knowingly, its work lost. Refuses while any person record in
`/etc/porelo-host/people/` still holds a membership, naming each person and their memberships with `"Take the project
off"` and `"Purge"`. Once no membership remains, it takes the homeserver, the VM pool and the forge off the host and
removes any legacy VPN files last. Every step takes down only what is there, so `down` after a failed `up` works
too. **The firewall stays on,** so that a machine kept after `down` does not expose the next service unasked; `down` ends by saying so, with the command that takes it off.

[SSH access](ssh.md) describes the key source, revocation input and Unix socket permissions.
