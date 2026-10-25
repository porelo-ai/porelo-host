# The host playbook

Brings a Porelo project up on a server and takes it down again, owned or rented by the hour: the Ansible collection
`porelo.host`, run on the host itself with `-c local` and the [JSON line callback](lines.md) `porelo.host.lines`.

**`porelo.host.up`, in two plays around the person's step.** The first play runs `base` (packages, KVM with libvirt,
podman), `porelo`'s install and setup script (which makes Porelo's account with linger and subordinate ids), `base`'s
account part (the account in `kvm` and `libvirt`, and the person's ssh key on the account for the stop), `drive` (the
`noexec` folder, and the drive's client syncing the person's folder when logged in: Tresorit's, the one provider
implemented today), and `porelo setup` with
`porelo vault status`. Each role that needs the person's step adds what is missing (`drive`, `vault-new` or `vault`) to
`porelo_host_needs`. The second play stops first with a [waiting line](lines.md) while `porelo_host_needs` is not
empty; once the drive is synced and the vault is open, it runs `vpn` (WireGuard with the host's key read from the drive
by `wg` itself, and nftables leaving only ssh and the VPN on the public interfaces), `porelo`'s project part (keys from
the drive into the vault, `project follow --signed-by`), `forge` and `vm_pool` where the host settings ask for them,
and `porelo`'s agents part (every offered agent and the project's transport packages installed, with no task started
or stop for a sign-in). A second `up` runs both plays from the top and changes only what differs, read from the
commands' own exit codes and `--json` output, so resuming is idempotence, with no marker file of the playbook's own.

Where the host runs a forge, `~/.config/porelo/ca-certificates.pem` of Porelo's account keeps the forge's CA in a
marked block beside the person's certificates, and `~/.config/porelo/task-ca-certificates.pem` holds that CA alone;
both are mode `0600` in the account's `0700` Porelo configuration directory. `down` removes the marked block and the
task CA file, and removes the account's CA bundle if only whitespace remains.

**`porelo.host.down`, the other way round.** Takes the VM pool and the forge off the host, stops every running task
of the account with `porelo task stop --all` and clears
the vault (`porelo vault clear --yes`), stops the VPN, waits for the drive to finish syncing before logging the client
out with `--unlink` and unmounting the folder, and takes the person's ssh key off the account last. Every step takes
down only what is there, so `down` after a failed `up` works too.
