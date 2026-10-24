# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
