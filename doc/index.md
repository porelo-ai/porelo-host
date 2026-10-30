# The host playbook

Brings a Porelo project up on a server and takes it down again, owned or rented by the hour: the Ansible collection
`porelo.host`, run on the host itself with `-c local` and the [JSON line callback](lines.md) `porelo.host.lines`.

**`porelo.host.up`, in two plays around the person's step.** The first play runs `base` (packages, KVM with libvirt,
podman), `porelo`'s install and setup script (which makes Porelo's account with linger and subordinate ids), `base`'s
account part (the account in `kvm` and `libvirt`, and the person's ssh key on the account for the stop), `porelo setup`
with `porelo vault status`, `vpn`'s needs part (whether the host's VPN key is there), and, where the host runs a forge,
`forge`'s request part (whether a certificate signed by the person's CA holds for it). Each role that needs the person's
step adds what is missing (`vault-new` with `keys`, `vault`, `wireguard` or `forge-certificate`) to `porelo_host_needs`.
The second play stops first with a [waiting line](lines.md) while `porelo_host_needs` is not empty; the person's stop
gives every need on [standard input](lines.md), from their secrets file on the desktop. Once the vault is open, it runs
`vpn` (WireGuard with the host's key, which the stop wrote into `/etc/wireguard`, read by `wg` itself, and nftables
leaving only ssh and the VPN on the public interfaces), `porelo`'s project part (the machine file read from
`/etc/porelo-host/setup/`, where the interface uploaded it, each key of the machine file checked in the vault, where the
stop put it, `project follow --signed-by`), `forge` and `vm_pool` where the host settings ask for them, and `porelo`'s
agents part (every offered agent and the project's transport packages installed, with no task started or stop for a
sign-in). A second `up` runs both plays from the top and changes only what differs, read from the commands' own exit
codes and `--json` output, so resuming is idempotence, with no marker file of the playbook's own.

**`porelo.host.bring` and `porelo.host.join`, in the person's own account.** The project admin runs
`ansible-playbook -c local porelo.host.bring -e porelo_project=<project>` on the host as themselves, with no `sudo` but
sync's; a developer runs `porelo.host.join` the same way. Both read the setup the interface uploaded into
`~/.local/share/porelo-host/setup/<project>/`: `machine.yml`, `project.bundle` and `access.bundle`, the directory the
person's own of mode `0700` below directories nobody else can write, each file their own plain file of mode `0600`;
a link, a missing file or another owner or mode is refused, naming what was found. The machine file names the project
at `project.bundle` and `access: {bundle: access.bundle}`. Then `porelo setup`, the vault the person's stop opened
(`porelo-host-stop --stdin`, run without `sudo`), Porelo's inventory, each key in the vault, `porelo project verify` on
both bundles from the commits in force, and `project follow --signed-by` with the keys pinned. The bring's machine file
also names `forge: {repositories: [{name, url}, ...]}`, which a join's must not. With the person's own forge token, taken
from their vault into their runtime directory for the run alone, the bring migrates each repository into the project's
organization (registered first by `porelo-host-project add`) with the central token the stop left there, protects
`main` (fast-forward only, one approval from `Owners` or `developers`), makes the teams `developers`, `gates` and
`agents`, and sets the Actions variables. Both write `~/.config/porelo-host/push/<project>.conf` from the repositories
the forge lists with their `original_url`. The bring ends with `sudo -n porelo-host-person sync <project>`, a user
timer that runs it again for each upload, and the project's room through `porelo talk room` once Porelo has it (B314).

The [local forge](local-forge.md) connects task branches and independent builds to the person's merge and gathered-push
decisions.

Where the host runs a forge, `~/.config/porelo/ca-certificates.pem` of Porelo's account keeps the forge's CA in a
marked block beside the person's certificates, and `~/.config/porelo/task-ca-certificates.pem` holds that CA alone;
both are mode `0600` in the account's `0700` Porelo configuration directory. `down` removes the marked block and the
task CA file, and removes the account's CA bundle if only whitespace remains.

Forgejo is bounded to 2 CPUs of time, 2 GiB of memory and 1024 processes and threads; its runner daemon to 1 CPU,
512 MiB and 256. The runner takes 2 jobs at once, and each gets 4 CPUs of time, 8 GiB and 2048 processes and threads,
with `OMP_NUM_THREADS=4` to tell tools its core count; these are fixed role defaults, independent of the host's size.
Before writing the runner's configuration, `up` refuses jobs that, with the VM pool, would take more than half the
host: capacity × CPUs per job above half the processors, or capacity × memory per job plus the pool's memory above
half of `MemTotal`, naming both sides.
`up` refuses Porelo's account, and the forge's two accounts where it runs, if their user managers lack any of
`cpu`, `memory` and `pids`, naming the account and every missing controller. Before changing libvirt or making VMs,
it also refuses a pool whose memory (systems × accounts per system × memory per VM) exceeds half of `MemTotal`,
naming the pool's memory and the host's total memory.

**`porelo.host.down`, the other way round.** Refuses first, before stopping anything, while any person record in
`/etc/porelo-host/people/` still holds a membership, naming each person and their memberships with `"Take the project
off"` and `"Purge"`. Once no membership remains, it takes the homeserver, the VM pool and the forge off the host and
closes the VPN last. Every step takes down only what is there, so `down` after a failed `up` works
too.
