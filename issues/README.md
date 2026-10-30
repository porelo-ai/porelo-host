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
| <a id="ho42"></a>[HO42](HO42-The-Host-Prepared-With-No-Project-Or-Person.md) | L | - | The host admin prepares a host with no project or person: the VPN per host, the shared forge, runner, pool and Matrix homeserver, under the host's names and the host admin's constrained CA. The homeserver's certificate waits on the homeserver serving one made elsewhere. |
| <a id="ho44"></a>[HO44](HO44-A-Project-Registered-On-The-Host.md) | M | [HO42](#ho42) | `porelo-host-project`: a project's forge organization and publisher with its pinned signing key, deleted once nothing is unpushed. |
| <a id="ho43"></a>[HO43](HO43-A-Project-Admin-Admitted-By-The-Host-Admin.md) | L | [HO42](#ho42) | `porelo-host-person`: a person admitted from their public keys (account, laptops' ssh keys and VPN peers, forge login and identities, Matrix token), locked and purged. |
| <a id="ho12"></a>[HO12](HO12-The-VM-Pool.md) | L | - | Role `vm_pool`: VMs with run accounts `porelo-machines` rents from, made by the same code as the test VM, deleted by name at `down`. |
| <a id="ho49"></a>[HO49](HO49-The-Persons-Forge-Login-Without-Repositories.md) | S | - | Wherever the host runs its own forge, the person's login and the password script are there, repositories or none. |
| <a id="ho45"></a>[HO45](HO45-The-Project-Brought-And-Joined-In-The-Persons-Own-Account.md) | L | [HO43](#ho43), [HO44](#ho44) | `bring.yml` and `join.yml` in the person's own account, with the stop's own-account mode and two bundles. |
| <a id="ho53"></a>[HO53](HO53-No-Forge-User-Operator.md) | S | [HO42](#ho42) | `up` makes no forge user `operator` and removes it from a host set up before, once a search shows nothing reads it; each person's login is their own. |
| <a id="ho55"></a>[HO55](HO55-A-Person-Leaves-When-No-Membership-Is-Left.md) | M | [HO43](#ho43), [HO44](#ho44) | Each person holds memberships, per project and by hand; removing a project locks whoever has none left, and `down` refuses while anyone holds one, naming each. |
| <a id="ho46"></a>[HO46](HO46-The-Developers-Kept-In-Step-With-The-Signed-Access-File.md) | L | [HO45](#ho45) | `sync`: the developers on the host kept to the signed `access.yml`, verified by Porelo's own check as a throwaway user, added or locked. |
| <a id="ho47"></a>[HO47](HO47-The-Gathered-Push-Run-By-Any-Developer.md) | S | [HO45](#ho45) | `porelo-host-push` as a user tool with the person's own config and token. |

## Implementing

| # | Size | Blocked by | What it covers |
|---|---|---|---|
| <a id="ho48"></a>[HO48](HO48-Every-Role-Tested-On-One-Host.md) | L | [HO46](#ho46), [HO47](#ho47) | The Molecule scenario with a host admin, two project admins and a developer with two laptops, every act and refusal. |

## Backlog

| # | Size | Blocked by | What it covers |
|---|---|---|---|
| <a id="ho14"></a>[HO14](HO14-The-Collections-Python-Under-Ansible-Test-Sanity.md) | S | - | `ansible-test sanity` on the collection's Python in the Build, from a pinned image of its own. |
| <a id="ho07"></a>[HO07](HO07-The-Projects-Store-Restored-And-Kept.md) | L | [HO37](#ho37) | Role `store`: restic pinned, each entry's own copy and restore command, an hourly timer of root's, a last copy at `down`, the restore before anything reads it. |

## Analyzed

| # | Size | Blocked by | Open questions | What it covers |
|---|---|---|---|---|
| <a id="ho52"></a>[HO52](HO52-Snapshots-Resolved-With-A-Read-Only-Token.md) | M | [HO44](#ho44) | 0 | Each project organization holds a `read:package` token as `PORELO_PACKAGES_READ_TOKEN` and its own `MAVEN_SNAPSHOTS_URL`, so builds resolve snapshots without the publisher's token. |

## Accepted

| # | Size | Blocked by | What it covers |
|---|---|---|---|
| <a id="ho59"></a>[HO59](HO59-An-Interrupted-Bring-Replaced-Safely.md) | M | - | A bring leaves `bring.state` in its setup directory, so an interrupted one is recognized and replaced by a new upload instead of refused. |
| <a id="ho56"></a>[HO56](HO56-Remove-Takes-The-Persons-Push-And-Sync-Away.md) | M | [HO46](#ho46), [HO47](#ho47) | Removing a project takes the push config and the sync timer out of each person's own account. |
| <a id="ho57"></a>[HO57](HO57-The-Bring-Checks-With-The-Keys-In-Force-After-A-Handover.md) | S | - | A second bring verifies only what is new since the followed commit, with `following --json`'s `signed_by_keys`. |
| <a id="ho22"></a>[HO22](HO22-Ssh-Reached-Only-Through-The-VPN-Once-It-Is-Up.md) | - | - | Once the VPN is up, the host's ssh answers only on the VPN's address, with a written, tried way back in when the VPN fails. |

## Idea

| # | Size | Blocked by | What it covers |
|---|---|---|---|
| <a id="ho58"></a>[HO58](HO58-The-Services-Podman-Kept-Small.md) | - | - | Once a day, and after a missed day, each service account's Podman loses the images and volumes no container used for a set time. |
| <a id="ho54"></a>[HO54](HO54-The-Host-Helpers-Hardened.md) | - | - | The stop's certificate and path checks, the people's SSH drop-in read first, a project registration retried after a forge timeout, and the password helper held to the project helper's checks. |
| <a id="ho51"></a>[HO51](HO51-Down-Names-What-A-Transport-Left.md) | - | - | Where `down` cleared the vault past a transport, its protocol names that transport and project in Porelo's words. |
| <a id="ho40"></a>[HO40](HO40-The-Build-Runs-On-The-Hosts-Forge-As-On-GitHub.md) | - | - | The move's builds on the host's forge: `build.yml` green on the host's Forgejo and on GitHub unchanged, with task branches built, the tools without `podman run`, snapshots by variable and Molecule on a machine with KVM. |
| <a id="ho39"></a>[HO39](HO39-The-Hosts-Agent-Works-In-A-Porelo-Task.md) | - | [HO40](#ho40) | porelo-host's agent, `Agent Host`, in a Porelo task on the move's host, with a way back: the image from `porelo.yml`. |
| <a id="ho30"></a>[HO30](HO30-The-Forges-Trust-And-Job-Bounds-Measured.md) | - | - | A running job's container measured to carry its bounds, and when Porelo reads the forge's CA, beyond what Molecule reads from the files the roles write. |
| <a id="ho28"></a>[HO28](HO28-The-Forges-Events-Routed-To-Each-Accounts-Porelo.md) | - | - | Optional speed-up: the forge's webhooks, reviews included, reported to one router on the host, which checks the signature and hands only a wake-up hint to the daemon of the account whose task it concerns, known from the pusher's forge account or the pull request's branch. |
| <a id="ho27"></a>[HO27](HO27-The-Forges-Jobs-Told-Where-The-Pool-Is.md) | - | - | The forge's runner tells every job where the VM pool is, so one workflow takes a pool account on the forge and rents a server on GitHub. |
| <a id="ho24"></a>[HO24](HO24-The-Setup-Runs-To-Its-End-On-The-Host.md) | - | - | `up`'s playbook runs on the host to its end whoever watches, and `porelo-host` attaches to it again when started again. |
| <a id="ho15"></a>[HO15](HO15-The-Host-On-Fedora.md) | - | - | The host on Fedora as on Ubuntu 26.04: SELinux, firewalld, `dnf` and a Molecule scenario on Fedora to measure. |

## Estimated

| # | Size | Blocked by | What it covers |
|---|---|---|---|
| <a id="ho23"></a>[HO23](HO23-A-Machine-Rented-And-Given-Back-By-OpenTofu.md) | L | - | An administrator rents and gives back a host by one OpenTofu module per provider, its state kept encrypted with the administrator, outside the interface. |

## Finished

| # | Title | What was built |
|---|---|---|
| <a id="ho50"></a>HO50 | Down Gives Back When Only A Transport Could Not Clear | `down` clears the vault and gives the server back where only a transport could not clear what it keeps, through `porelo vault clear --json`, and with `--force` in a step of its own where Porelo kept the vault for its transports; any other refusal still stops it. |
| <a id="ho37"></a>HO37 | The Host's Secrets Given On Standard Input At The Stop | The secrets the stop names given from `secrets.kdbx` by a desktop terminal through `keepassxc-cli`, the interface holding none, in one root pipeline of base64 lines, each passed straight to its user; the WireGuard key and every token off the drive. |
| <a id="ho36"></a>HO36 | The Host Reads The Files Its Setup Uploaded | The host's setup reads nothing from the drive: `machine.yml` and the project's bundle uploaded by the interface into `/etc/porelo-host/setup/`, root's and readable by the account alone, refused where the account can write them, removed at `down`. |
| <a id="ho38"></a>HO38 | The Drive Leaves The Host's Setup | Nothing of Tresorit on a host: the drive's role, its installer module and the stop's `drive` go, so `up` asks no login and `down` waits on no sync; a user's own drive is the interface's per-user setup. |
| <a id="ho35"></a>HO35 | The Forge Opened In The Browser Once The VPN Is Up | Once the VPN is up, the person opens the forge in their browser and signs in with their lasting password: the `/etc/hosts` line, one lasting name-constrained CA installed once whose key stays off the host's disk, and the password kept in `secrets.kdbx` and set over ssh on each new forge, in no host file. |
| <a id="ho41"></a>HO41 | The Host Joins The Project's Room On The Laptop | A rented host's tasks in the project's room on the laptop during the move: the hosts line for `matrix.porelo.internal`, and the host's registration token on the stop's standard input into the file the signed project names. |
| <a id="ho34"></a>HO34 | The Forge Merges Fast-Forward Only | Each repository on the host's forge offers only the fast-forward merge, read back after it is set, so a merged pull request's own commits reach `main` unchanged with the person as author and no commit of the forge's `operator`; the central work joins on a `central/take` branch. |
| <a id="ho33"></a>HO33 | The Forge's Runner Takes Jobs Side By Side, With A Cache | The forge's runner takes four jobs at once, refused by `up` where they would not fit half the machine's CPUs and memory beside the VM pool, and serves its cache on the forge's address, so a job's `actions/cache` saves and a later run restores. |
| <a id="ho32"></a>HO32 | The Gathered Push Refuses A Moved Central Forge | `porelo-host-push`, started by the person on the host over ssh, pushes each repository's local `main` to the central forge without force, the central token asked for hidden; a moved central forge is refused, named and brought back as `central/main`. |
| <a id="ho31"></a>HO31 | The Account's Gate And Reader On The Host's Forge | The gate of Porelo's account pushes `porelo/<task>` to the host's forge by name over TLS and the `forgejo` build reader reads its verdict and logs, the token in the account's vault alone; `main` is protected so only the person's approved and merged pull request reaches it. |
| <a id="ho29"></a>HO29 | The Person's Own Web Login On The Forge | The person signs in to the host's forge through the VPN as `operator`, an owner of the organization, with a generated first password fetched over ssh from a root-only file and changed at the first sign-in. |
| <a id="ho26"></a>HO26 | Each Agent's Own Forge Account | Each agent the host's settings name gets an account `agent-<name>` on the host's forge in team `agents`, which writes the organization's code, pull requests and issues, with a token written only into a root-only file on the host. |
| <a id="ho08"></a>HO08 | The Forge With Its Registry | Where the host's settings ask for it, `up` runs Forgejo with its Actions runner and package registry in rootless podman under two accounts of their own, reached by name over TLS with the host's CA through the VPN, its repositories migrated once from the central forge with no push mirror, and `down` takes it off. |
| <a id="ho17"></a>HO17 | The Forge's CA In Porelo's Account | `up` puts the forge's CA into Porelo's account, as a marked block in `~/.config/porelo/ca-certificates.pem` for host clients and alone in `~/.config/porelo/task-ca-certificates.pem` for tasks, and `down` takes it out. |
| <a id="ho20"></a>HO20 | Every Container Of The Host Fits The Machine | The forge, its runner and each job are bounded by fixed CPU, memory and process limits, and `up` refuses an account without the `cpu`, `memory` and `pids` controllers and a VM pool larger than half the host's memory. |
| <a id="ho25"></a>HO25 | The Stop Asks Again Until It Is Done | At `up`'s stop, `porelo-host-stop` asks a mistyped Tresorit login or vault passphrase again in the same terminal until it succeeds or the person cancels, with exits the interface reads. |
| <a id="ho21"></a>HO21 | Each Step Says What It Does And How Long | Each of the playbooks' sixteen steps carries a plain-words text and its usual duration as its own variables, which its `started` line passes on after a plan line of the run ahead, `v` staying 1. |
| <a id="ho13"></a>HO13 | A Release Carries Its Tarball And Digest | A release attaches the collection's tarball and its `SHA256SUMS`, stopping before anything is attached if the tag is not `galaxy.yml`'s plain version, so `host up` can refuse any other. |
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

## Rejected

| # | Title | Why |
|---|---|---|
| <a id="ho16"></a>HO16 | The Person's Drive On OneDrive | The host has no drive any more; OneDrive as a user's own drive may come later as a new idea beside the interface's. |
