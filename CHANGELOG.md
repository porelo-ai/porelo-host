# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- The collection `porelo.host`, built with `ansible-galaxy collection build` into a tarball that holds only what it
  ships; no role yet.
- The playbook `porelo.host.up`, run on the host itself with `-c local`.
- The role `porelo.host.base`: the host's packages, KVM with libvirt and podman, stopping on a CPU without
  virtualization before it installs anything; and, once Porelo's setup made the account, that account in KVM's and
  libvirt's groups.
