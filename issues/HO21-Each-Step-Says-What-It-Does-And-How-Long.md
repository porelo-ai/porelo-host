# HO21 — Each Step Says What It Does And How Long

**Status:** Accepted.
**Size:** S - a text and a duration per step in the collection, and two fields in the step lines; the interface's
part is porelo-frontend's.

**What must be true.** Every step a person waits on while `up` or `down` runs carries a text in plain words, such as
"Installing Porelo and the agents", and how long it usually takes. The step lines `porelo-host` reads carry both. The
interface shows them and writes no text of its own for a step the collection defines.

## Plan, nothing decided

- **Where the texts live:** in the collection, beside the steps they name, so a step and its words change in one
  commit. One text per step a person notices, a role or a block of tasks, not one per Ansible task.
- **The step lines:** `plugins/callback/lines.py` adds the text and the usual duration to a step's `started` line,
  as fields of the same JSON line, its version raised. A step without a text passes as today.
- **The usual duration:** first a value per step written by hand from today's measured runs; later one learned from
  measured runs. Where it is kept and who learns it is to decide.
- **Who writes what, agreed with porelo-frontend:**
  - this repository: the texts and durations of the collection's steps, and the step lines;
  - porelo-frontend: the texts of `porelo-host`'s own steps before the playbook (`rent`, `ssh`, `copy`), written by
    its `packages/porelo_host` into the same step lines, and showing what the lines carry in porelo-frontend
    [F154](https://github.com/porelo-ai/porelo-frontend/blob/main/issues/README.md#f154) and
    [F161](https://github.com/porelo-ai/porelo-frontend/blob/main/issues/README.md#f161), whose views write no step
    text of their own.
- **Red first:** a step with a text whose line lacks it, and a line whose version did not change.

## Acceptance

- Each step a person waits on during `up` and `down` shows its text and usual duration in the step lines, read in a
  Molecule run's output.
- A step without a text still gives the line it gives today.
