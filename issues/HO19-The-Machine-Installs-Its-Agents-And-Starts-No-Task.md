# HO19 — The Machine Installs Its Agents And Starts No Task

**Status:** Accepted; blocked by porelo's machine file naming the agents to install, in place of its tasks.
**Size:** M - the `porelo` role's task part and `down`, and the Molecule scenario's flow from converge to side_effect.

**What must be true.** `up` installs the agents the machine file names and starts no task, with no stop for an agent's
sign-in; the person starts and stops tasks on the machine by hand or from the interface, signing an agent in when a
task needs it; `down` stops every running task of the account before the vault is cleared, whoever started it.

## Plan

- **`tasks.yml` becomes the agents' part**: the packages of the agents the second inventory names, and those of the
  transports the project names, installed through the same `dpkg-query` and setup script `--with` steps; no
  `agent-login:<agent>` stop and no `porelo task start`. It still stops unless the vault reads open.
- **`down.yml`** stops every running task of the account by Porelo's own answer, before `vault clear`; how Porelo lists
  them or stops them all is asked of porelo's agent (`porelo task list` has no machine-readable form today).
- **The Molecule scenario**: converge loses the stop for the stub's sign-in; verify starts the stub's task itself, as
  the person does, and reads it running; side_effect reads that `down` stopped a task the machine file never named.
- **Red first**: side_effect against today's `down`, which stops only the machine file's tasks, with a task started by
  hand left running.

## Acceptance

- After `up` on the test VM: the named agents' packages are installed, no task exists, and no waiting line names an
  agent.
- A task started by hand after `up` runs; after `down` it is stopped and the vault is gone.

## To be checked

- The machine file's and the inventory's field for the agents, as porelo's `doc/hosts.md` settles it.
- Porelo's answer for every running task of the account.
