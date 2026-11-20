# HO198 — Playbooks And Programs Only Map

```json
{
  "$schema": "issue-1.json",
  "id": "HO198",
  "title": "Playbooks And Programs Only Map",
  "state": "Accepted",
  "size": "S",
  "priority": "High",
  "rank": 1,
  "blockedBy": [],
  "covers": "`down.yml` checks its inventory and calls roles, its give-back check with the follow paused moving into a role, and `porelo-host-measure`'s `main` maps its arguments to one call, the lock and the result's publication moving behind it."
}
```

**Why this size.** One playbook's tasks move into a role, and one program's `main` into a function, both with the
tests they already have; no contract another repository reads.

**What must be true.** An entry point only checks its input, maps it, calls one piece that does the work and maps
the answer back. The piece that does the work is tested without the entry point. In this repository the entry points
are the playbooks `up`, `down` and `measure`, and the programs `porelo-host-check` and `porelo-host-measure`. Read
against this:

- `up.yml`, `measure.yml` and `porelo-host-check` already map: they check the inventory or the arguments and call
  roles or one function.
- `down.yml` runs the use case "may this host go down" itself. It reads whether projects exist, asks
  `porelo-host project give-back-check`, includes the people check, pauses the follow's timer and waits for an active
  follow, asks both again, then resumes the follow on a refusal and fails. That is a lock, a rule and a recovery, in
  the entry point.
- `porelo-host-measure`'s `main` holds the run's guard and publication beside parsing its arguments: the given
  labels' rule, the machine's obstruction, the measuring lock under `/run`, signal handling, and the result written
  to a temporary file and published by `link(2)`.

## Plan

- **The give-back check becomes a role's task file** (`roles/porelo/tasks/give_back_check.yml`, called by
  `include_role` with `tasks_from`): read, ask, pause the follow, ask again, resume and fail on a refusal. `down.yml`
  keeps its inventory asserts and calls it once. The forge's uninstall, planned in the issue that installs and
  uninstalls the forge and Matrix alone, calls the same file instead of a copy.
- **`porelo-host-measure`:** `main` parses and maps to one `measure(options, machine)`, which holds the lock, the
  signals and the publication. Its unit tests call `measure` without `argparse`.
- **Red first:** a unit test over `measure` alone, where a lock already present refuses with exit 1 and leaves the
  lock. Today that path is reachable only through `main`. The Molecule scenario `default`, whose side effect runs `down`, stays green unchanged, which
  shows the moved check behaves as before.

## Acceptance

- The new unit test, seen red first, the unit suite, sanity and the Molecule `default` scenario green.
- `down.yml` holds no task but its inventory asserts and role calls.
