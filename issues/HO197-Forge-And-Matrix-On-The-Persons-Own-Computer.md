# HO197 — Forge And Matrix On The Person's Own Computer

```json
{
  "$schema": "issue-1.json",
  "id": "HO197",
  "title": "Forge And Matrix On The Person's Own Computer",
  "state": "Analyzed",
  "size": "L",
  "priority": "High",
  "rank": 2,
  "blockedBy": ["HO196"],
  "covers": "On a person's own Ubuntu computer with Porelo from apt, the window installs and uninstalls the forge and Matrix with one administrator prompt each, by the same part playbook a host runs, from the collection Porelo's apt repository ships; nothing of a host's hardening is applied there, and uninstalling leaves the computer as it was."
}
```

**Why this size.** It needs several pieces: the collection as a Debian package with a root-owned entry command, an
inventory for this computer, a switch that keeps a host's hardening off a personal computer, a record of what an install
added so its uninstall leaves the computer as it was, and an acceptance run on a fresh Ubuntu VM. It is L because it
crosses Agent Core's apt repository and Agent Frontend's window.

**What must be true.** A person with Porelo from apt clicks Install on a part's page, confirms one administrator prompt
and sees the installation's lines live. The part then runs on this computer as it does on a host. Uninstall asks the
same way and leaves the computer as it was before that part's install. The person's own login keeps working as
before: no firewall rule, no ssh setting, no removed KVM, no changed controllers. Nothing a person or an agent could
write is run as root: the prompt runs a fixed command from a package, never a playbook from a user's directory.

## Plan

- **Package:** `porelo-host-collection`, built by this repository's release workflow and published to Porelo's apt
  repository beside `porelo-host`.
  - It installs the collection under `/usr/share/porelo-host/collection` and depends on Ubuntu's `ansible-core`.
  - It ships the entry `/usr/libexec/porelo-host/part`, which takes only `forge|matrix` and `install|uninstall`,
    writes its inventory itself, and runs `part.yml` with `-c local` and the lines callback.
- **The administrator step:** the window runs `pkexec /usr/libexec/porelo-host/part <part> <action>`. A polkit action
  shipped in the package names only that path. One prompt per action.
- **The inventory for this computer:**
  - `porelo_host_name` is the computer's own name, made one DNS label.
  - `porelo_host_network` and the other host settings take fixed values, since a computer reaches its parts over the
    Unix sockets alone.
  - A new switch, `porelo_host_personal: true`.
- **`base` with `porelo_host_personal`:**
  - Installs only podman, its packages and the subordinate ids.
  - Skips the nftables firewall, sshd's `Match Group`, the KVM removal, controller delegation beyond what rootless
    podman needs, and the legacy VPN.
  - The check role asks for the same.
- **People:** the person's own account joins `porelo-people`, recorded as on a host, so the socket gates admit it. A
  new group takes effect only at the next login, so either the window says so once, or the gate admits the account by
  its uid.
- **What install added:** each package and group the install added, that was not there before, is recorded under
  `/var/lib/porelo-host/added/<part>`. Uninstall removes what it recorded and nothing else, and only once no other part
  still needs it.
- **Red first:**
  - a test that the entry refuses any other argument and any environment it does not set itself;
  - a test that `base` with `porelo_host_personal` contains no firewall, sshd or KVM task.

## Acceptance

- The red-first tests above pass.
- On a fresh Ubuntu VM with Porelo from apt, a listing of packages, groups, files and units is taken first. Matrix,
  then the forge, are installed through the package's entry under pkexec, then both are uninstalled. The listing
  afterwards equals the first one.
- The window's install shows the lines live, and a second install changes nothing.

## Open questions

- Whether the forge on a person's own computer follows the person's organization like a host's forge, which needs the
  organization's token in the computer's vault, or holds only the person's own work until it is brought to central.
  The story's test brings work to central from it, so following seems meant; this decides the vault step.
- Whether the person's account in `porelo-people` waits for the next login, said once by the window, or the gate on
  this computer admits the person's account by its uid.

## To be checked

- With Agent Core: publishing `porelo-host-collection` in Porelo's apt repository, and a review of the polkit action.
- With Agent Frontend: how the window runs pkexec and reads the lines, and how it shows the next-login note.
- Whether Forgejo's runner on a personal computer needs the VM pool, or runs its jobs in podman alone.
