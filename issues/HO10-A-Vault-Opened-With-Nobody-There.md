# HO10 — A Vault Opened With Nobody There

**Status:** Estimated; blocked by porelo [B209](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b209).
**Size:** XS - the playbook only checks that the vault is open and stops if not; opening it is the caller's, through
Porelo's command.

**What must be true.** `up` runs from start to end without a person opening the vault over `ssh -t`, and the
passphrase still never lies on the host or the person's drive, and never passes through Ansible, its inventory, a
variable or a log.

## Plan

- **The playbook does not open the vault**: [HO09](README.md#ho09)'s second play already checks that it is open and
  stops with its own kind of refusal if not. The caller - `porelo-machines host up`, porelo-frontend - asks the
  person, runs `porelo vault unlock` over ssh with the passphrase on its standard input, and runs `up` again.
- **What changes here**: the stop's line names that command in the form the caller runs it, besides the `ssh -t` one
  a person types; nothing in the playbook reads, holds or passes the passphrase.
- **Red first**: the second play against a shut vault must stop before it deposits anything; already [HO09](README.md#ho09)'s test.

## Acceptance

- On [HO03](README.md#ho03)'s VM: `up`, the stop, the vault opened over ssh with the passphrase on standard input,
  `up` again to the end; the passphrase appears in no output of the run and in no file on the host.
