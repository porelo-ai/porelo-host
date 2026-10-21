# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
  vault and its project followed by its signature, the tasks' agents installed, a stop with `agent-login:<agent>`
  for each agent whose sign-in the vault lacks, and the tasks started; at `down`, the tasks stopped and the vault
  cleared.
