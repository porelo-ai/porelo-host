# Issues

What is open in this repository, ordered by what to do next rather than by number. The number is
identity, not sequence.

**Grouped by state**, each group's heading naming it, as the shared rules set them out; within a group
the order is the priority. Only the operator sets Accepted, Rejected, Estimated, Backlog, Rework and
Finished; this repository's agent sets Analyzed, Implementing and Review, and proposes the rest in the
channel.

Its prefix is `HO`. *Open questions*, in *Analyzed* only, counts what waits on the operator. A group with nothing in
it is left out.

## Review

| # | Size | Blocked by | What it covers |
|---|---|---|---|
| <a id="ho05"></a>[HO05](HO05-The-VPN.md) | M | - | Role `vpn`: WireGuard with the host's key read from the drive by `wg` itself, nftables leaving only ssh and the VPN public. |
| <a id="ho06"></a>[HO06](HO06-The-Persons-Drive-Mounted.md) | M | - | Role `drive`: Tresorit's headless client syncing one tresor into a `noexec` folder, the login the person's, `down` waiting until it is synced. |
| <a id="ho09"></a>[HO09](HO09-Up-And-Down-In-Their-Order.md) | M | - | `up.yml` in two plays around the person's one stop, `down.yml` the other way round, resuming by idempotence, the room copied before `vault clear`, one JSON line per step for a program. |

## Implementing

| # | Size | Blocked by | What it covers |
|---|---|---|---|
| <a id="ho08"></a>[HO08](HO08-The-Forge-With-Its-Registry.md) | L | porelo [B233](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b233), porelo [B234](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b234) (tasks' side only) | Role `forge`: Forgejo and its runner in rootless podman under two accounts of their own, on the VPN and the tasks' address only, its registry over TLS from a CA made on the host, the project's repositories migrated from the central forge with push mirrors, credentials made and kept on the host, every build publishing with a publisher's token kept as an Actions secret; run where the host setting `porelo_host_forge` asks for it. |
| <a id="ho02"></a>[HO02](HO02-Porelos-Own-Commands-Called-Never-Redone.md) | L | - | Role `porelo`: the package, the account, `porelo setup`, keys from the drive into `porelo vault put` on the host, `follow --signed-by`, `task start`; idempotent by Porelo's own answers, no secret through Ansible; `up` pauses for the person to open the vault. |

## Backlog

| # | Size | Blocked by | What it covers |
|---|---|---|---|
| <a id="ho07"></a>[HO07](HO07-The-Projects-Store-Restored-And-Kept.md) | L | porelo-project [PJ45](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj45), porelo-message-matrix [MX24](https://github.com/porelo-ai/porelo-message-matrix/blob/main/issues/README.md#mx24), porelo [B231](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b231) | Role `store`: restic pinned, each entry's own copy and restore command, an hourly user timer, a last copy at `down`, the restore before anything reads it. |

## Idea

| # | Size | Blocked by | What it covers |
|---|---|---|---|
| <a id="ho15"></a>[HO15](HO15-The-Host-On-Fedora.md) | - | - | The host on Fedora as on Ubuntu 26.04: SELinux, firewalld, `dnf` and a Molecule scenario on Fedora to measure. |
| <a id="ho16"></a>[HO16](HO16-The-Persons-Drive-On-OneDrive.md) | - | - | OneDrive in Tresorit's place for the person's drive, chosen per project: client, login, encryption and sync to measure. |

## Estimated

| # | Size | Blocked by | What it covers |
|---|---|---|---|
| <a id="ho11"></a>[HO11](HO11-The-Homeservers-Packages.md) | XS | - | The Matrix transport's and homeserver's packages installed, nothing enabled; the first task start brings the homeserver up. |
| <a id="ho12"></a>[HO12](HO12-The-VM-Pool.md) | L | - | Role `vm_pool`: VMs with run accounts `porelo-machines` rents from, made by the same code as the test VM, deleted by name at `down`. |
| <a id="ho10"></a>[HO10](HO10-A-Vault-Opened-With-Nobody-There.md) | XS | porelo [B209](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b209) | `up` to the end with the vault opened by the caller over ssh with the passphrase on standard input; the playbook only checks and stops. |
| <a id="ho13"></a>[HO13](HO13-A-Release-Carries-Its-Tarball-And-Digest.md) | S | - | A release attaches the collection's tarball and its `SHA256SUMS`, so `host up` can refuse any other; the check itself is porelo-frontend's. |
| <a id="ho14"></a>[HO14](HO14-The-Collections-Python-Under-Ansible-Test-Sanity.md) | S | - | `ansible-test sanity` on the collection's Python in the Build, from a pinned image of its own. |

## Finished

| # | Title | What was built |
|---|---|---|
| <a id="ho01"></a>HO01 | The Collection's Skeleton | `porelo.host` builds into a tarball checked to hold only what it ships, and its Build runs the documents' checks, yamllint and ansible-lint from one image pinned by digest. |
| <a id="ho03"></a>HO03 | Molecule Tests On A Throwaway VM | `build/molecule.sh` tests the roles on a libvirt VM made and deleted for each run, here and in the Build on GitHub's runner, leaving nothing after a failure or an interrupt. |
| <a id="ho04"></a>HO04 | The Host's Base: Packages, KVM, Podman | The role `porelo.host.base` installs the packages, KVM with libvirt and podman, stopping on a CPU without virtualization first, and puts Porelo's account into KVM's and libvirt's groups. |
