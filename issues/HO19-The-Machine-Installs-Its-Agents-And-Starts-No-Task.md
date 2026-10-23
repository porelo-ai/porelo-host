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

## Built

- The role reads inventory version 2 and installs every missing agent of the setup script's `--list --json`,
  stopping when it lists none, with the project's transport and homeserver packages; it keeps the stop unless the
  vault reads open, starts no task and has no sign-in stop. `down` stops on a `vault status` other than 0, 3 or 4
  where Porelo is installed, runs `porelo task stop --all` where a task can have run, and only then clears the vault.
  The scenario checks, after `up`, no container of the account, every catalogue agent installed by dpkg and the
  list not empty, each provider's candidate from Porelo's source, and the homeserver still disabled; verify installs
  the stub, signs it in and starts its task by hand; after `down`, no running container of the account.
- Green on the test VM with porelo [B258](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b258)'s
  packages handed over (`3ff8994e`, `0.5.1~snapshot.934+local`), 2026-10-23 11:12Z-11:29Z, all five stages, idempotence `changed=0`. The first `up` took 3 min 30 s with every agent of the
  catalogue installed, the second 55 s, so installing them costs about 2 min 35 s on a new host (inferred from the two
  runs). Seen red first: with `down`'s stop of every task skipped, side_effect found a running container of the
  account after `down` (11:30Z-11:47Z).
- **Declined:** a test of `porelo task stop --all` ending 70: no container can be made to survive it honestly in the
  scenario, and `vault clear` refusing past a running task holding a token is the guard behind it.

## Acceptance

- After `up` on the test VM: every agent package of Porelo's repository is installed, no task exists, and no waiting
  line names an agent; the time `up` spends installing them is measured and said.
- A task started by hand after `up` runs; after `down` it is stopped and the vault is gone.
