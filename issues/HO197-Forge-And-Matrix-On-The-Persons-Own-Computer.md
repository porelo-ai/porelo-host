# HO197 — Forge And Matrix On The Person's Own Computer

```json
{
  "$schema": "issue-1.json",
  "id": "HO197",
  "title": "Forge And Matrix On The Person's Own Computer",
  "state": "Estimated",
  "size": "L",
  "priority": "High",
  "rank": 2,
  "blockedBy": ["HO196"],
  "covers": "On a person's own Ubuntu computer with Porelo from apt, the window installs and uninstalls the forge and Matrix with one administrator prompt each, by the same part playbook a host runs, from the collection Porelo's apt repository ships; nothing of a host's hardening is applied there, and uninstalling leaves the computer as it was."
}
```

**Why this size.** It needs several pieces: the collection as a Debian package with a root-owned entry command, an
inventory for this computer, a switch that keeps a host's hardening off a personal computer, the person admitted by
uid instead of a group, the organization's follow with its waiting stop, a record of what an install
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
  - The release uploads the `.deb` over REST into Artifactory's `porelo-dist-deb`, under
    `pool/main/p/porelo-host-collection/`, with the properties `deb.distribution=<channel>`, `deb.component=main` and
    `deb.architecture=amd64`, without which it is stored but never indexed. It refuses a version already in
    `dists/releases/main/binary-amd64/Packages`, and waits until the index shows the new one. It needs its own
    `JF_ACCESS_TOKEN` secret, which the operator grants.
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
- **The person:** on the person's own computer no `porelo-people` group is made or joined. The forge's gate in the
  `porelo-host` package and the Matrix gate in the Matrix transport admit the one account the part's settings name,
  by its uid from the socket's peer credentials, so the person needs no new login. The entry writes that account,
  the one that ran pkexec (`PKEXEC_UID`), into the settings; a host's gates keep admitting `porelo-people`.
- **The organization:** the computer's forge follows the person's organization as a host's does. The install takes
  `porelo`'s organization part, and its waiting stop asks for the organization's token, which the person puts into
  the computer's vault through `porelo vault`, as on a host; nothing of the token passes through the entry or the
  inventory.
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

## To be checked

- The polkit action file and the `part` entry, handed to Agent Core by commit for a reading: what the action allows,
  `auth_admin` or `auth_admin_keep`, that it names the one path and no argument pattern, and what `part` accepts.
- With Agent Frontend: how the window runs pkexec and reads the lines.
- With Agent Core and Agent Matrix: each gate admitting the one account its settings name, by uid, beside the
  `porelo-people` group it admits on a host.
- Whether Forgejo's runner on a personal computer needs the VM pool, or runs its jobs in podman alone.
