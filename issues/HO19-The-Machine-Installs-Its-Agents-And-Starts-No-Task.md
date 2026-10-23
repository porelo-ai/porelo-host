# HO19 — The Machine Installs Its Agents And Starts No Task

**Status:** Implementing; blocked by porelo [B258](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b258).
**Size:** M - the `porelo` role's task part and `down`, and the Molecule scenario's flow from converge to side_effect.

**What must be true.** `up` installs every agent Porelo's repository offers and starts no task, with no stop for an
agent's sign-in; the person starts and stops tasks on the machine by hand or from the interface, signing an agent in
when a task needs it; `down` stops every running task of the account before the vault is cleared, whoever started it.

## Plan

- **`tasks.yml` becomes the agents' part**: Porelo's setup script's `--list --json` names every package of kind
  `agent` that Porelo's own repository offers; each not installed is installed with `--with`, as the transports'
  packages the second inventory names are. No `agent-login:<agent>` stop and no `porelo task start`. It still stops
  unless the vault reads open.
- **The second inventory is read at `porelo_inventory_version` 2**, which names no tasks; any other version stops the
  play with what it read.
- **`down.yml`** runs `porelo task stop --all` as the account before `vault clear`: 0 goes on, 70 stops the play with
  Porelo's words naming what still runs.
- **The Molecule scenario**: converge loses the stop for the stub's sign-in; verify installs `porelo-agent-stub` and
  starts its task itself, as the person does, and reads it running; side_effect reads that `down` stopped a task the
  machine file never named.
- **Red first**: side_effect against today's `down`, which stops only the machine file's tasks, with a task started by
  hand left running.

## Acceptance

- After `up` on the test VM: every agent package of Porelo's repository is installed, no task exists, and no waiting
  line names an agent; the time `up` spends installing them is measured and said.
- A task started by hand after `up` runs; after `down` it is stopped and the vault is gone.
