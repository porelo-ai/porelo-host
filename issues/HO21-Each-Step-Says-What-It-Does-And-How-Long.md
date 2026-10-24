# HO21 — Each Step Says What It Does And How Long

**Status:** Backlog.
**Size:** S - two fields on a step's `started` line and one line of the whole run ahead, read from the playbook
tasks' own variables, a text and a duration on each of the playbooks' sixteen steps, tests and the contract's page; no
role changes.

**What must be true.** Every step a person waits on while `up` or `down` runs carries a text in plain words, such as
"Installing Porelo and the agents", and how long it usually takes. The step lines `porelo-host` reads carry both. The
interface shows them and writes no text of its own for a step the collection defines. Before the first step, one line
names every step of the run ahead with its text and duration, so the interface shows the whole run's time left.

## Plan

- **A step is a task of the playbook itself**, not of a role: `up` has ten, `down` six, each an `include_role` whose
  own tasks give lines too. Today `up`'s first play runs `porelo.host.base` under `roles:`, which gives no step of its
  own; it becomes an `include_role` task like the others, so every role runs under one step.
- **The words live on the step, as its variables**, so a step and its words change in one commit:

      - name: Install Porelo and run its setup script for the account
        ansible.builtin.include_role: ...
        vars:
          porelo_host_step:
            text: Installing Porelo
            seconds: 90

  `playbooks/up.yml` and `playbooks/down.yml` gain one such block per step. A role's inner task carries none, nor
  does `up`'s stop for the person, which gives its waiting line.
- **The line:** `plugins/callback/lines.py`'s `v2_playbook_on_task_start` reads `task.vars["porelo_host_step"]`
  untemplated, as the playbook wrote it, and adds `text` and `seconds` to that task's `started` line. A string `text`
  and a non-negative integer `seconds` pass; anything else is left out, never guessed, so a mistyped block shows as a
  step without words, which the test of the playbooks below catches. A task without the block gives today's line.
- **The run ahead:** before the first step's `started` line, the callback writes one line
  `{"v": 1, "state": "plan", "steps": [{"task": "…", "text": "…", "seconds": …}, …]}`, in `up` and in `down` alike:
  every step of the playbook's plays that carries the block, in order, a step under `when:` (the forge, the pool) only
  where the host settings ask for it. `task` is the name its `started` line will carry, so a reader matches a step by
  name, never by position; a step without a usual duration leaves `seconds` out. It
  is an added kind of line, so `v` stays 1; `doc/lines.md` says a reader skips a `state` it does not know. A resumed
  `up` runs from the top and ends what is done quickly, so the total is an upper bound. The line's form is agreed with
  porelo-frontend for [F154](https://github.com/porelo-ai/porelo-frontend/blob/main/issues/README.md#f154).
- **The texts are English only.** A key to translate them by would be another added field, not part of this issue.
- **The version stays 1:** `doc/lines.md` says an added field keeps it. A program tells a step from a role's inner task
  by `text` being there; the inner tasks' lines that follow belong to the step before them.
- **The durations** are written by hand from a measured Molecule run of `up` and `down` on the test VM, rounded up to
  ten seconds; learning them from runs is not part of this issue.
- **`doc/lines.md`** shows the `started` line with both fields and says which tasks carry them; the changelog gains the
  entry under *Added*.
- **Who writes what, agreed with porelo-frontend:**
  - this repository: the texts and durations of the collection's steps, and the step lines;
  - porelo-frontend: the texts of `porelo-host`'s own steps before the playbook (`rent`, `ssh`, `copy`), written by
    its `packages/porelo_host` into the same step lines, and showing what the lines carry in porelo-frontend
    [F154](https://github.com/porelo-ai/porelo-frontend/blob/main/issues/README.md#f154) and
    [F161](https://github.com/porelo-ai/porelo-frontend/blob/main/issues/README.md#f161), whose views write no step
    text of their own.
- **Red first**, in `tests/unit/plugins/callback/test_lines.py` with a play of its own: a run whose first line is not
  the `plan` line naming its steps in order, a step under a false `when:` listed; a task with the block whose
  `started` line lacks `text` and `seconds`; a block with a wrong type that still gives a field; and a test that loads
  `playbooks/up.yml` and `playbooks/down.yml` and fails on a step of the playbook without a valid block.

## Acceptance

- Each of the sixteen steps of `up` and `down` gives a `started` line with its `text` and `seconds`, read in a
  Molecule run's output.
- A task without the block, and every inner task of a role, still gives the line it gives today, with `v` 1.

## To be checked

- How the callback reads the steps and decides their `when:` before the first task runs: from the plays at
  `v2_playbook_on_start` with the play's variables, or from one first task of `up` that gathers the blocks into a fact
  the callback writes; measured on the host's `ansible-core`.

- How a step's duration is measured in a Molecule run: the lines carry no time, so either the run's output is
  timestamped as it is read, or a timing callback runs beside `porelo.host.lines`, if the tools image carries one.
- That `task.vars` holds an `include_role` task's `vars:` untemplated at task start on the host's `ansible-core`.
