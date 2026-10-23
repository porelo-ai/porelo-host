# HO11 — The Homeserver's Packages

**Status:** Implementing.
**Size:** S - two packages installed in `tasks.yml` of the `porelo` role, and the scenario gains a checkpoint before the
sign-in and a real homeserver start.

**What must be true.** Where the project names the Matrix transport, its homeserver can come up at the first task
start, and the playbook itself starts nothing of it.

## Plan

- **Installed, never run**: `porelo-message-transport-matrix` and `porelo-matrix-homeserver` are packages; the second
  is a disabled systemd user unit running Tuwunel in rootless podman on 127.0.0.1, with no federation, which the
  transport's `setup` brings up at the first task start of a project that names `mail.transports.matrix`. In
  [HO02](README.md#ho02)'s `tasks.yml`, the one `dpkg-query` and setup script `--with` task pair installs the packages
  the tasks need - the tasks' agent packages, every `porelo_transports[].package` from `porelo project inventory`, and
  `porelo-matrix-homeserver` when a transport's scheme is `matrix` - before the stop for agents' sign-ins, and enables
  nothing; the account's linger is Porelo's setup script's.
- **Its state** is [HO07](README.md#ho07)'s to restore before that first start: the podman volume
  `porelo-matrix-homeserver`, `~/.config/porelo/matrix/homeserver.conf` and `registration-token`,
  `~/.local/state/porelo/matrix/backups`, and the poll positions under `~/.local/state/porelo/transports/matrix`; its
  accounts' tokens are in the vault.
- **Red first**: in `converge.yml`, after the `up` that stops for the agent's sign-in and before any task has started
  (not in `verify.yml`, since every `up` past the sign-in starts the task and `setup` enables the unit), assert both
  packages are installed and `porelo-matrix-homeserver` is `disabled` and `inactive`, failing when the role enables it;
  in `verify.yml`, assert the unit is `enabled` and `active` and `GET /_matrix/client/versions` on the port in
  `homeserver.conf` answers 200, failing when `porelo-matrix-homeserver` is left off the package list; in
  `side_effect.yml`, assert the unit is not `active` after `down`.

## Acceptance

- On the test VM `build/molecule.sh` makes: after `up`, both packages are installed, the unit is disabled, and the first
  `porelo task start` of a project naming the transport brings the homeserver up.

## Built

- `tasks.yml` installs one package list: the tasks' agent packages, every `porelo_transports[].package`, and
  `porelo-matrix-homeserver` where a transport's scheme is `matrix`, enabling nothing. The scenario's project names
  `mail.transports.matrix`. Green on the test VM against porelo-message-matrix's snapshot 74, 2026-10-23
  09:39Z-09:54Z, all five stages: before the sign-in both packages installed and the unit disabled and inactive;
  after the task start the unit enabled and active and `/_matrix/client/versions` answering on its port; after `down`
  the unit not active and `vault clear` ending 0. Seen red first with today's role: converge stopped at the packages'
  check (09:54Z-10:01Z).
  With the role enabling the unit, converge stopped at `is-enabled` reading `enabled` (10:02Z-10:08Z).
- **Measured by porelo-message-matrix's run:** a user manager started before the unit was installed loads it without
  `daemon-reload`; the first task start on a fresh account takes 36 s with the image pull, the homeserver active 9 s
  after the start.
- **Found on the way:** the test VM's name goes to lower case in `build/molecule.sh`, since the transport refused a
  machine name in upper case until porelo-message-matrix
  [MX31](https://github.com/porelo-ai/porelo-message-matrix/blob/main/issues/README.md#mx31); `vault clear` ended 1 on
  the transport's account-level `clear` until
  [MX32](https://github.com/porelo-ai/porelo-message-matrix/blob/main/issues/README.md#mx32).
