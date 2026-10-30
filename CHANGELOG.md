# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Person revocation tolerates missing Linux accounts, rejects shared purged keys, preserves lagging project cards,
  and validates lock retry dependencies.
- The runner comes back when its proxy restarts, a stopped proxy removes the jobs left in its namespace, and jobs get a
  read-only name table of root's and the host name localhost, so no job can take the forge's name for later jobs. The runner gate's Bearer
  support and its refusal of artifact v4 transfers are documented.
- Gathered push validates raw caller config bytes and opened descriptors, keeps Git helpers in its cleanup group,
  and handles early coprocess exits and NUL output safely.
- Gathered push refuses sudo callers of the root-only check, bounds caller configuration reads and isolates token
  helpers from credential stdin. Namespace forwarding preserves early gate responses on socket errors, times out
  idle sockets and stops Git descendants and removes temporary clones when the helper receives a signal.
- Project sync requires each person's key and expiry to match the applied host registry. SSH revocations remain
  cumulative, project removal clears membership and signer publications, and person locks preserve verified Matrix
  admins while attempting each service revocation independently. Forgejo team sessions include organization scopes,
  unlock skips absent identities, and lock and purge recover when a locked person's Linux account is gone.

### Changed

- Gathered push and pull run through sudo for the current project developer. Local API traffic uses the forge gate's
  Unix socket; each local Git transfer uses a private root network namespace and a credential pipe, with no host TCP
  listener, local CA or vault token. Migration stays in the person's account and obtains its local token on demand.

- Host persons come from verified cards with one SSH key and optional expiry. Project roles and locks reconcile
  forge teams, Matrix rooms and project-local allowed signers; other projects and sessions stay. Host locks,
  current-key revocation and last-membership removal end sessions and revoke forge tokens. Purged logins cannot
  return. Replaced signer keys remain bounded to their historical validity.
- SSH on port 22 is the public entry point. Root-owned key files, an atomically published KRL, private person
  return-socket directories and forwarding restrictions replace VPN access. Lock ends sessions and the user manager;
  the registry reader can supply card keys, expiries and host-wide revocations through the person helper.

### Removed

- Device records, per-device credentials and addresses, and credential stdin for person admission. Project sync no
  longer reads access-file host CA values or grants commit-signing authority to the project's verification key.
- The VPN role and the WireGuard stop. Up and down remove a legacy WireGuard interface and its files.

### Added

- Matrix clients use the transport's system socket gate as `porelo-matrix`, restricted to `porelo-people`.
  The homeserver uses a private Unix socket, with gate preparation before startup and no role-managed TLS or TCP
  publication. Project sync atomically publishes verified room admins, project removal deletes them, and purge
  expels the login through the transport. Admission no longer issues Matrix machine or registration tokens.
- Separate Unix socket gates for browser and token-authenticated Git/API access to Forgejo. Browser identity comes
  from the admitted host account; caller identity headers are removed and browser credential-setting routes refused.
  Forgejo uses a private Unix socket with no TLS or SSH listener; certificate requests and the password helper go.
- Host task certificate recording, lookup by task key fingerprint, per-task forge token creation and deletion, and a
  daily expiration sweep. Certificate validation uses OpenSSH and the person's current key in the applied registry;
  records are private and append-only. The gate consumer migration remains pending.
- On-demand person forge tokens answered directly on stdout, token-free admission, and all-token deletion on registry
  revocation with retry after an API failure. Bring's earlier token-file consumer still requires migration.
- `porelo-host-person registry`, run by root or `sudo -n` by the host admin pinned once at setup with `registry pin
  <login> <key>`, takes the host's projects and persons from the registry bundle the host admin uploads into
  `~/.local/share/porelo-host/setup/registry.bundle`: Porelo's `registry verify` checks it in the sync's isolated unit
  against the pinned key and the last applied commit, refusing a foreign signer or an older or forked state whole. Bad
  entries are named alone while the rest applies, a revoked login stays revoked, a verified handover moves the pin,
  and the answer is recorded root-only in `/etc/porelo-host/registry/applied.json`. A project the registry no longer
  names for its admin is named in the answer and kept.

- `porelo-host-person sync <project>`, callable by root or `sudo -n` by the project's unlocked recorded admin through
  the `porelo-people` sudoers rule, copies the admin's plain private `project.bundle` and `access.bundle` into a
  root-only `/run/porelo-host/sync/` directory and verifies them through `porelo project verify --json` in a
  `DynamicUser` transient unit without home or network against the project's pinned signing keys and last applied
  commits. Verified persons determine project memberships, SSH card keys, forge teams, Matrix rooms and allowed
  signers; removal locks an account when its last membership ends. Sync records `commit=`, `access_commit=` and
  bundle-verification `signer=` lines in `/etc/porelo-host/projects/<project>.conf`.
- `porelo-host-project` registers a project for a recorded person, with its pinned SSH Ed25519 signing key, forge
  organization and package-only publisher. Removal checks every repository's commits against the central forge
  before deleting its repositories, packages, organization, publisher and root-only record.
- A root person helper admits project admins with root-owned SSH key files
  and private records, and locks or purges their host accounts. Admission creates their forge login and gate, and
  makes no forge token. Lock disables the forge identities and deletes their tokens, expels Matrix accounts and revokes registration in one operation, and removes delivered
  credentials and their runtime directory. A separate install task provides the helper, SSH key lookup and a
  no-argument forge-password sudo rule.
- `porelo.host.bring` and `porelo.host.join` run in the person's own account with no `sudo` but sync's: the setup's
  files in `~/.local/share/porelo-host/setup/<project>/` checked, Porelo's verify on the project and access bundles
  and the project followed; the bring migrates the project's repositories with the admin's own forge token, protects
  `main`, makes the teams `developers`, `gates` and `agents`, sets the Actions variables, runs `sync` with a user
  timer and makes the room once Porelo can; both write the person's push config. `porelo-host-stop --stdin`, run
  without `sudo`, gives the caller's own `vault-new`, `vault`, `keys`, `forge-central-token` and `identities`.
- `up` installs every agent package the repository publishes, read from the packages providing `porelo-agent`, and
  Porelo's message filter with rootless networking; a repository publishing no agent stops `up`.

### Changed

- `porelo-host-person sync <project>` and `porelo-host-project add <project> <admin>` refuse a project the applied
  registry does not name for that admin.

- The forge runner, registration and jobs share a loopback proxy to a dedicated token-only gate socket. Checkout,
  package access and the Actions cache no longer depend on the VPN address or published runner ports; jobs no longer
  receive forge CA trust mounts. Existing runner registrations keep their token and use the loopback web port.

- `porelo-host-push <project> [<repository>...]` runs in any project developer's own account (refusing root and `sudo`
  with `77`), reading `~/.config/porelo-host/push/<project>.conf` (`0600` plain file in a `0700` directory of the
  caller's `getent passwd` home, never `$HOME`) and the caller's `<forge_name>.person` token from their vault (refusing
  a missing entry with `69`, naming it and `porelo-host-stop --stdin identities`) while prompting hidden on the terminal
  for their central forge token; without repository names it pushes every repository in the config's order. `up`
  installs `/usr/local/sbin/porelo-host-push` (`0755`) and `/etc/porelo-host/forge/central-ca.conf` (`0644`), and
  `porelo-host-project remove`'s `--check` reads each repository's central address from Forgejo's `original_url`
  instead of `/etc/porelo-host/forge/push.conf`, refusing any repository without one by name.
- Person records in `/etc/porelo-host/people/` store ordered `member=hand` and `member=<project> project-admin|developer`
  memberships in place of `role=` and `projects=`; an existing `role=project-admin` record with no `member=` line is
  read as `member=hand` and rewritten on its next write. `porelo-host-person add` records `member=hand`, `lock` keeps
  memberships, `porelo-host-project add` records `member=<project> project-admin` for any unlocked member, and
  `porelo-host-project remove` drops the project's memberships, locks anyone left with none, and reports `"locked"` in
  its JSON answer. `porelo.host.down` checks `/etc/porelo-host/people/` first and refuses before stopping anything
  while any record holds a membership, naming each person and their memberships with `"Take the project off"` and
  `"Purge"`.

### Removed

- `/etc/porelo-host/forge/push.conf`: `up` no longer writes root's shared push configuration, and nothing reads it.
- Admission makes no `<agent>-<user>` forge identity, and `up` no longer writes `agents=` into
  `/etc/porelo-host/forge.conf`: Porelo lends agents no forge identity of their own. Lock still revokes those a 6j
  host made.
- The default `operator` forge login, `forge_person`, `person=` in `/etc/porelo-host/forge.conf`, and direct-root calls
  to `porelo-host-forge-password` (now refused with `64` unless run through `sudo` as an admitted person). On an
  existing host, `up` deletes a forge user `operator` that has no record in `/etc/porelo-host/people/` and rewrites
  `forge.conf` without `person=`, so a person named `operator` can be admitted like anyone else.

### Fixed

- A failed admission after the account exists leaves the person locked and recorded, so purge can remove them; a
  failed purge leaves the account expired. A locked person can neither be admitted again without purge nor own a new
  project. A forge failing in itself is reported as something missing (69). SSH reads the people's keys as soon as
  `up` has written its drop-in.
- A sudo call to the forge-password helper changes only the caller's own login and requires their unlocked,
  root-owned person record.
- SSH for the `porelo-people` group reads only root's VPN-restricted authorized keys, so a person cannot add an
  unrestricted key in their home. Other accounts retain their existing key lookup.
- `down` gives the host back when only a room's transport could not clear what it keeps with the vault, such as a
  homeserver taken off the VPN before the give-back. An open vault is then cleared with `--force` in a step of its own
  name; anything else Porelo does not remove still stops `down`. It needs Porelo's `vault clear --json`.

## [0.5.8] - 2026-10-28

### Fixed

- The host comes back from a reboot: the firewall's unit leaves systemd's default ordering, which on an image running
  cloud-init's network stage before `sysinit.target`, such as Scaleway's Ubuntu, closed a cycle that held the boot.
- `up` follows the project again when the interface uploads a newer bundle at the same path: before, a commit the
  person signed after the first `up` stayed unfollowed, since only a changed address or key led to a new follow.
- The forge's runner takes 2 jobs at once by default, not 4, so `up` with the defaults passes the capacity check on the
  16 processors of the server Porelo rents instead of refusing it.

## [0.5.7] - 2026-10-28

### Added

- The host joins the project's room on the person's own computer during the move: the VPN role writes the marked
  line `<the person's VPN address> matrix.porelo.internal` into `/etc/hosts`, the stop takes `--stdin matrix-token`
  into the account's `~/.config/porelo/matrix/host-registration-token`, `up` refuses with `matrix-token:` while a
  project naming that file finds it missing, and `down` removes both.

### Changed

- The person's forge login and `porelo-host-forge-password` come with every forge on a host, whether repositories are
  migrated into it or not; only the organization's `Owners` team waits for the repositories.
- The host's `/etc/hosts` stays out of the account's containers on every host, with its own forge or without one.

## [0.5.6] - 2026-10-28

### Removed

- Nothing of Tresorit is on a host any more: the role `drive`, the module `tresorit_installer`, the drive's step in
  `up` and `down`, and the stop's `drive` and `--email`, which `porelo-host-stop` now refuses with 64. `up` asks no
  drive login and `down` waits on no sync; a user's own drive is the interface's, outside the host's setup.

### Security

- `tresorit_installer` in 0.5.1 to 0.5.5 checked that the installer's signature covers the file from line 3 on, but
  ran the file from line 1, which it never checked: whoever controlled the download could put a command on line 1 and
  still pass every check. The module is gone with the drive; a host set up by those releases with a drive ran an
  installer checked that way.

### Changed

- The host's forge takes its certificate from the person's lasting CA, made once on their desktop with a name
  constraint, whose key never reaches a host: `up` makes a key and a request and names `forge-certificate` at the stop,
  `porelo-host-stop --request` prints the request, and the signed certificate comes back on standard input, checked
  before it is written. No CA key and no first password file are made on the host any more; the person's lasting
  password is set by `porelo-host-forge-password` from standard input, over ssh.
- The stop's secrets come on its standard input: `porelo-host-stop --stdin NEED...`, run as root over the admin's ssh,
  takes the vault's passphrase, the machine's keys, the host's VPN key and the central forge's token from the person's
  secrets file, one base64 line each, checks every line before using any, and pipes each value straight into its user.
  The drive holds no secret any more.
- `up`'s stop names `keys` with `vault-new` and `wireguard` while the host has no VPN key. `project` no longer puts
  keys from the drive into the vault; it refuses naming each key of the machine file the vault lacks.
- The host's VPN key lies in `/etc/wireguard/porelo-host.key`, root's with mode `0600`, so the VPN comes back after a
  reboot; `down` removes it. The AppArmor rule that let `wg` read the drive's key is gone.
- The host reads the machine file and the project's bundle from `/etc/porelo-host/setup/`, where the interface uploads
  them root's alone before `up`, no longer from the drive. `install` lets the account read them, `project` refuses
  them where anybody but root can write them, naming owner and mode, and `down` removes them.
- `up` refuses naming `forge-central-token` only while a repository is still to migrate, and the migration removes the
  token from `/run/porelo-host/` again. `forge_central_token_path` is gone.

## [0.5.5] - 2026-10-27

### Added

- The forge's runner takes `forge_runner_capacity` jobs at once, 4 by default, in place of one. `up` refuses a capacity
  whose jobs, with the VM pool, would take more than half the host's processors or memory, naming both sides.
- A job's `actions/cache` reaches the runner's cache on the forge's address, through two fixed ports published there,
  so a second run restores what the first saved instead of starting cold.

### Changed

- Each repository on the host's forge merges pull requests by fast-forward only, every other merge style off, and
  `up` reads the setting back. A merged pull request leaves its own commits on `main` unchanged; the forge no longer
  makes a merge commit authored by the person's forge account, which the pushed commits' check refused.

## [0.5.4] - 2026-10-27

### Added

- The host resolves `forge.porelo.internal` over loopback TLS and installs the Forgejo build reader. With repositories
  configured, the forge creates `porelo-<account>` in `gates`, pipes its token directly into Porelo's vault as
  `git.token.forge.porelo.internal`, and protects each `main` against direct pushes, requiring the person's approval
  and merge with no administrator override. A matching rule and existing vault entry stay unchanged across `up`;
  `down` removes the host's marked name mapping. Porelo's account's containers no longer copy the host's
  `/etc/hosts`, so tasks resolve the forge through Porelo's resolver alone.
- The forge gives the person an `operator` web login in the organization's `Owners` team, with a generated first
  password in root-only `/etc/porelo-host/forge/person.password` and a required password change at first sign-in.
  Existing accounts keep their passwords across `up`; `down` removes the first password file.
- The forge gives the person `porelo-host-push`, run with `sudo` on the host: it pushes each named repository's local
  `main` to its central forge without force, the central token asked for each time and kept nowhere. A central forge
  that moved refuses it; the command names the central commits, brings them to the local forge as `central/main`, and
  pushes none of the repositories after it. It trusts the central forge by the system's CAs, or by
  `porelo_host_forge_central_ca`, never by the host's own. `down` removes the command and its settings.

### Changed

- The README links the host lifecycle and the local forge's documentation.

## [0.5.3] - 2026-10-25

### Removed

- The forge no longer configures push mirrors to the central forge, since they force-push and can erase its commits.

### Added

- The forge gives configured agents their own accounts, repository write access and root-only token files kept across up.
- The forge's runner offers `ubuntu-24.04` and `ubuntu-26.04` labels on a pinned act image and fetches actions from
  github.com by their workflow pins. It sets the organization's Actions variables `PORELO_PUBLISH` to `false`,
  `PORELO_DEPLOY_PROFILE` to `forge-release` and `MAVEN_SNAPSHOTS_URL` to the forge's Maven registry, with a placeholder
  `JF_URL` and a placeholder `JF_ACCESS_TOKEN` secret created only when absent; every job's JDK trusts the host's CA
  through a read-only passwordless PKCS12 store set by `JAVA_TOOL_OPTIONS`; the runner offers the pinned Temurin 25 as
  `JAVA_HOME_25_X64`, as GitHub's image does.
- Fixed CPU, memory and process bounds for Forgejo, its runner daemon and jobs; `up` refuses accounts missing
  delegated controllers and VM pools that would use more than half the host's memory.
- The forge's CA is installed in Porelo's account for the broker and tasks, preserving the person's certificates;
  `down` removes the forge's trust from both files.
- The forge answers on port 443 of the host's loopback, for tasks, and of the VPN's address, through a root-owned
  socket that forwards to rootless Forgejo; its URLs carry `https://forge.porelo.internal/` with no port.

## [0.5.2] - 2026-10-24

### Added

- `porelo-host-stop` completes the host's drive login and vault step in the person's terminal, asking again after
  a failed attempt until it succeeds or the person cancels.

## [0.5.1] - 2026-10-24

### Changed

- `up` installs every agent Porelo's repository offers and starts no task, with no stop for a sign-in; `down` stops
  every running task of the account before clearing the vault.
- `porelo.host.lines`: a failed step's line carries the command's own words, a loop's by each failed item, cut to
  their tail; a task with `no_log` stays hidden.

### Added

- `porelo.host.lines`: a step's own words and usual duration on its `started` line, and one plan of the described
  steps across all plays before the run, leaving out steps whose conditions are false.
- A release made from a tag `v<version>` attaches the collection's tarball and a `SHA256SUMS` naming its digest; a tag
  that is not `galaxy.yml`'s plain version stops it before anything is attached.
- The collection `porelo.host`, built with `ansible-galaxy collection build` into a tarball that holds only what it
  ships; no role yet.
- The playbook `porelo.host.up`, run on the host itself with `-c local`, in two plays around the step only the person
  can take, and `porelo.host.down`, the order its steps come in.
- The stdout callback `porelo.host.lines`: one JSON line per step, and a waiting line naming what the person's step
  must give, for a program that runs the playbooks.
- The role `porelo.host.base`: the host's packages, KVM with libvirt and podman, stopping on a CPU without
  virtualization before it installs anything; and, once Porelo's setup made the account, that account in KVM's and
  libvirt's groups.
- The role `porelo.host.porelo`, everything through Porelo's own commands: Porelo installed by its pinned key with
  its setup script, `porelo setup`, a stop while the vault is missing or shut, the machine file's keys put into the
  vault and its project followed by its signature, every offered agent installed without starting a task or stopping
  for a sign-in; at `down`, every running task of the account stopped and the vault cleared.
- The role `porelo.host.forge`, where the host setting `porelo_host_forge` asks for it: Forgejo with its registry and
  its runner in rootless podman under accounts of their own, HTTPS on the VPN's address alone with a CA made on the
  host, the repositories `porelo_host_forge_repositories` names migrated once with push mirrors back, the person's
  token for the central forge read from their drive by the shell alone, and every build, an unreviewed task branch's
  too, publishing into the registry with the token of the account `porelo-publisher`, kept as the organization's
  Actions secret `PORELO_PUBLISHER_TOKEN` and never read out; stopped at `down`, keeping nothing.
- The role `porelo.host.vm_pool`, where the host setting `porelo_host_vm_pool` asks for it: one libvirt VM per run
  account from each system's cloud image by its pinned digest, its pool file mounted read-only into the forge
  runner's jobs and its run key kept on the host alone and handed to jobs as the forge organization's Actions secret
  `PORELO_POOL_SSH`, and each VM reverted on the host to its live base snapshot when `sudo porelo-pool-give-back`
  powers it off; at `down`, the secret and the VMs with their snapshots, disks, seeds, keys and file deleted.
- In `porelo.host.porelo`, the transports a project names and Matrix's homeserver installed through Porelo's setup
  script, enabling nothing.
