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
| <a id="ho01"></a>[HO01](HO01-The-Collections-Skeleton.md) | M | - | `porelo.host` as a collection at the root: `galaxy.yml`, `meta/runtime.yml`, yamllint and ansible-lint, a tarball checked to hold only what ships, a Build on a GitHub runner with the documents' checks, the tools from one image pinned by digest; built, the Build on GitHub left. |

## Backlog

| # | Size | Blocked by | What it covers |
|---|---|---|---|
| <a id="ho03"></a>[HO03](HO03-Molecule-Tests-On-A-Throwaway-VM.md) | M | - | One ansible-native Molecule scenario whose `create` and `destroy` make and remove a libvirt VM per run, Ubuntu 26.04 with nested KVM, leaving nothing after a failure too. |
| <a id="ho04"></a>[HO04](HO04-The-Hosts-Base-Packages-KVM-Podman.md) | S | - | Role `base`: the packages, KVM usable by the account, rootless podman with lingering; stops first on a CPU without virtualization. |

## Estimated

| # | Size | Blocked by | What it covers |
|---|---|---|---|
| <a id="ho09"></a>[HO09](HO09-Up-And-Down-In-Their-Order.md) | M | - | `up.yml` in two plays around the person's one stop, `down.yml` the other way round, resuming by idempotence, the room copied before `vault clear`, one JSON line per step for a program. |
| <a id="ho06"></a>[HO06](HO06-The-Persons-Drive-Mounted.md) | M | - | Role `drive`: Tresorit's headless client syncing one tresor into a `noexec` folder, the login the person's, `down` waiting until it is synced. |
| <a id="ho05"></a>[HO05](HO05-The-VPN.md) | M | - | Role `vpn`: WireGuard with the host's key read from the drive by `wg` itself, nftables leaving only ssh and the VPN public. |
| <a id="ho02"></a>[HO02](HO02-Porelos-Own-Commands-Called-Never-Redone.md) | L | porelo [B208](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b208) | Role `porelo`: the package, the account, `porelo setup`, keys from the drive into `porelo vault put` on the host, `follow --signed-by`, `task start`; idempotent by Porelo's own answers, no secret through Ansible; `up` pauses for the person to open the vault. |
| <a id="ho11"></a>[HO11](HO11-The-Homeservers-Packages.md) | XS | - | The Matrix transport's and homeserver's packages installed, nothing enabled; the first task start brings the homeserver up. |
| <a id="ho07"></a>[HO07](HO07-The-Projects-Store-Restored-And-Kept.md) | L | porelo-project [PJ45](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj45), porelo-message-matrix [MX24](https://github.com/porelo-ai/porelo-message-matrix/blob/main/issues/README.md#mx24) | Role `store`: restic pinned, each entry's own copy and restore command, an hourly user timer, a last copy at `down`, the restore before anything reads it. |
| <a id="ho08"></a>[HO08](HO08-The-Forge-With-Its-Registry.md) | M | - | Role `forge`: Forgejo, its runner and registry in rootless podman on the VPN only, mirrors of the project's repositories, credentials made and kept on the host. |
| <a id="ho12"></a>[HO12](HO12-The-VM-Pool.md) | L | - | Role `vm_pool`: VMs with run accounts `porelo-machines` rents from, made by the same code as the test VM, deleted by name at `down`. |
| <a id="ho10"></a>[HO10](HO10-A-Vault-Opened-With-Nobody-There.md) | XS | porelo [B209](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b209) | `up` to the end with the vault opened by the caller over ssh with the passphrase on standard input; the playbook only checks and stops. |
