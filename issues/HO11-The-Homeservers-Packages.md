# HO11 — The Homeserver's Packages

**Status:** Estimated.
**Size:** XS - two packages installed in one task file of the `porelo` role, and a check; no contract of its own.

**What must be true.** Where the project names the Matrix transport, its homeserver can come up at the first task
start, and the playbook itself starts nothing of it.

## Plan

- **Installed, never run**: `porelo-message-transport-matrix` and `porelo-matrix-homeserver` are packages; the second
  is a disabled systemd user unit running Tuwunel in rootless podman on 127.0.0.1, with no federation, which the
  transport's `setup` brings up at the first task start of a project that names `mail.transports.matrix`. A task
  file `matrix.yml` in [HO02](README.md#ho02)'s role installs the two packages when the inventory names the
  transport, and enables nothing; the account's linger is Porelo's setup
  script's.
- **Its state** is [HO07](README.md#ho07)'s to restore before that first start: the podman volume
  `porelo-matrix-homeserver`, `~/.config/porelo/matrix/homeserver.conf` and `registration-token`, and the poll
  positions under `~/.local/state/porelo/transports/matrix`; its accounts' tokens are in the vault.
- **Red first**: `verify.yml` asserts the unit is installed and not enabled after `up` without a task start; it fails
  when the role enables it.

## Acceptance

- On the test VM `build/molecule.sh` makes: after `up`, both packages are installed, the unit is disabled, and the first
  `porelo task start` of a project naming the transport brings the homeserver up.
