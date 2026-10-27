# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- The stop's secrets come on its standard input: `porelo-host-stop --stdin NEED...`, run as root over the admin's ssh,
  takes the vault's passphrase, the machine's keys, the host's VPN key and the central forge's token from the person's
  secrets file, one base64 line each, checks every line before using any, and pipes each value straight into its user.
  The drive holds no secret any more; only the drive's own login stays the person's, typed at the host.
- `up`'s stop names `keys` with `vault-new` and `wireguard` while the host has no VPN key. `project` no longer puts
  keys from the drive into the vault; it refuses naming each key of the machine file the vault lacks.
- The host's VPN key lies in `/etc/wireguard/porelo-host.key`, root's with mode `0600`, so the VPN comes back after a
  reboot; `down` removes it. The AppArmor rule that let `wg` read the drive's key is gone.
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
