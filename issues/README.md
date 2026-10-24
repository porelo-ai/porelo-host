# Issues

What is open in this repository, ordered by what to do next rather than by number. The number is
identity, not sequence.

**Grouped by state**, each group's heading naming it, as the shared rules set them out; within a group
the order is the priority. Only the operator sets Accepted, Rejected, Estimated, Backlog, Rework and
Finished; this repository's agent sets Analyzed, Implementing and Review, and proposes the rest in the
channel.

Its prefix is `HO`. *Open questions*, in *Analyzed* only, counts what waits on the operator. A group with nothing in
it is left out.

## Implementing

| # | Size | Blocked by | What it covers |
|---|---|---|---|
| <a id="ho21"></a>[HO21](HO21-Each-Step-Says-What-It-Does-And-How-Long.md) | S | - | Each of the playbooks' sixteen steps carries a plain-words text and its usual duration as its own variables, which its `started` line passes on for the interface to show, `v` staying 1. |
| <a id="ho13"></a>[HO13](HO13-A-Release-Carries-Its-Tarball-And-Digest.md) | S | porelo-buildtools' write for a release's publish job | A release attaches the collection's tarball and its `SHA256SUMS`, so `host up` can refuse any other; the check itself is porelo-frontend's. |
| <a id="ho08"></a>[HO08](HO08-The-Forge-With-Its-Registry.md) | L | porelo [B233](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b233), porelo [B234](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b234) (tasks' side only) | Role `forge`: Forgejo and its runner in rootless podman under two accounts of their own, on the VPN and the tasks' address only, its registry over TLS from a CA made on the host, the project's repositories migrated from the central forge with push mirrors, credentials made and kept on the host, every build publishing with a publisher's token kept as an Actions secret; run where the host setting `porelo_host_forge` asks for it. |
| <a id="ho12"></a>[HO12](HO12-The-VM-Pool.md) | L | porelo-buildtools [BT24](https://github.com/porelo-ai/porelo-buildtools/blob/main/issues/README.md#bt24) | Role `vm_pool`: VMs with run accounts `porelo-machines` rents from, made by the same code as the test VM, deleted by name at `down`. |

## Backlog

| # | Size | Blocked by | What it covers |
|---|---|---|---|
| <a id="ho14"></a>[HO14](HO14-The-Collections-Python-Under-Ansible-Test-Sanity.md) | S | - | `ansible-test sanity` on the collection's Python in the Build, from a pinned image of its own. |
| <a id="ho07"></a>[HO07](HO07-The-Projects-Store-Restored-And-Kept.md) | L | porelo-project [PJ45](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj45), porelo-message-matrix [MX24](https://github.com/porelo-ai/porelo-message-matrix/blob/main/issues/README.md#mx24), porelo [B231](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b231), porelo-message-matrix's backup taken as its own | Role `store`: restic pinned, each entry's own copy and restore command, an hourly user timer, a last copy at `down`, the restore before anything reads it. |

## Analyzed

| # | Size | Blocked by | Open questions | What it covers |
|---|---|---|---|---|
| <a id="ho23"></a>[HO23](HO23-A-Machine-Rented-And-Given-Back-By-OpenTofu.md) | L | - | 3 | An administrator rents and gives back a host by one OpenTofu module per provider, its state kept encrypted with the administrator, outside the interface. |

## Accepted

| # | Size | Blocked by | What it covers |
|---|---|---|---|
| <a id="ho17"></a>[HO17](HO17-The-Forges-CA-In-Porelos-Account.md) | XS | - | Role `porelo`: the host's forge CA in `~/.config/porelo/ca-certificates.pem` of Porelo's account where the forge runs, owner-only, so a task reaches the forge's API through the broker; `down` takes it out again. |

## Idea

| # | Size | Blocked by | What it covers |
|---|---|---|---|
| <a id="ho22"></a>[HO22](HO22-Ssh-Reached-Only-Through-The-VPN-Once-It-Is-Up.md) | - | - | Once the VPN is up, the host's ssh answers only on the VPN's address, with a written, tried way back in when the VPN fails. |
| <a id="ho15"></a>[HO15](HO15-The-Host-On-Fedora.md) | - | - | The host on Fedora as on Ubuntu 26.04: SELinux, firewalld, `dnf` and a Molecule scenario on Fedora to measure. |
| <a id="ho16"></a>[HO16](HO16-The-Persons-Drive-On-OneDrive.md) | - | - | OneDrive in Tresorit's place for the person's drive, chosen per project: client, login, encryption and sync to measure. |

## Estimated

| # | Size | Blocked by | What it covers |
|---|---|---|---|
| <a id="ho20"></a>[HO20](HO20-Every-Container-Of-The-Host-Fits-The-Machine.md) | M | - | The forge's and runner's quadlets, the runner's job containers and the VM pool bounded to fit a host of any size, porelo-project's [PJ68](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj68) for porelo-host. |

## Finished

| # | Title | What was built |
|---|---|---|
| <a id="ho19"></a>HO19 | The Machine Installs Its Agents And Starts No Task | `up` installs every package Porelo's setup script names as an agent, and the project's transports, without starting a task or stopping for a sign-in; `down` stops every running task of the account before `vault clear`. |
| <a id="ho18"></a>HO18 | A Failed Loop Says Why | A failed step's JSON line carries the command's own words after Ansible's, a loop's by each failed item's label, cut to their tail within fixed bounds, and a task with `no_log` stays hidden. |
| <a id="ho11"></a>HO11 | The Homeserver's Packages | `up` installs the Matrix transport's and homeserver's packages with the agents and enables nothing; the first task start brings the homeserver up. |
| <a id="ho10"></a>HO10 | A Vault Opened With Nobody There | `up` runs to the end with the vault opened beforehand by the caller over ssh, the passphrase on standard input; the playbook only reads `porelo vault status` and stops, and the Molecule scenario searches its output, the journal and the host's files for the secret. |
| <a id="ho01"></a>HO01 | The Collection's Skeleton | `porelo.host` builds into a tarball checked to hold only what it ships, and its Build runs the documents' checks, yamllint and ansible-lint from one image pinned by digest. |
| <a id="ho03"></a>HO03 | Molecule Tests On A Throwaway VM | `build/molecule.sh` tests the roles on a libvirt VM made and deleted for each run, here and in the Build on GitHub's runner, leaving nothing after a failure or an interrupt. |
| <a id="ho04"></a>HO04 | The Host's Base: Packages, KVM, Podman | The role `porelo.host.base` installs the packages, KVM with libvirt and podman, stopping on a CPU without virtualization first, and puts Porelo's account into KVM's and libvirt's groups. |
| <a id="ho05"></a>HO05 | The VPN | The role `porelo.host.vpn` brings WireGuard up with the host's private key read from the drive by `wg` itself under a local AppArmor rule, loads the `inet porelo_host` nftables table leaving only ssh and the VPN on the public interfaces, and stops the interface and removes its file at `down`. |
| <a id="ho06"></a>HO06 | The Person's Drive Mounted | The role `porelo.host.drive` mounts a `noexec` sparse-file filesystem for the drive, installs Tresorit's client once its signature under the pinned CA checks and runs its daemon as a user unit, stops `up` for `drive` while logged out, syncs only the person's tresor into the folder, and at `down` waits until it is synced before logging out with `--unlink` and unmounting. |
| <a id="ho09"></a>HO09 | Up And Down In Their Order | `playbooks/up.yml` runs in two plays around the waiting stop for what only the person can give and resumes from the top by idempotence, `playbooks/down.yml` takes down what is there in reverse order, and the stdout callback `porelo.host.lines` reports each task and stop as version 1 JSON lines. |
| <a id="ho02"></a>HO02 | Porelo's Own Commands Called, Never Redone | The role `porelo.host.porelo` installs Porelo by its pinned key and runs its setup script for the account, runs `porelo setup`, stops `up` while the vault is missing or shut, deposits the machine file's keys from the drive into `porelo vault put --from-file` and follows the project by its signature, and clears the vault at `down`, every step through Porelo's own commands and answers with no secret passing through Ansible. |
