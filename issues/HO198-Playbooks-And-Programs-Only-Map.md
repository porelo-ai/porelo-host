# HO198 — Playbooks And Programs Only Map

```json
{
  "$schema": "issue-1.json",
  "id": "HO198",
  "title": "Playbooks And Programs Only Map",
  "state": "Estimated",
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

Read in `playbooks/down.yml`, `roles/porelo/tasks/` and `porelo-host-measure`'s `main`.

- **`down.yml` keeps only its three inventory asserts** and calls roles. Its five tasks before the roles move:
  - The test mode is taken away first by `roles/porelo/tasks/test_mode.yml`, called with
    `porelo_host_test_switches: []`. That file already says an empty list takes the mode away, as down does, and it
    replaces a link instead of writing through it.
  - The rest becomes `roles/porelo/tasks/give_back_check.yml`. It reads whether `/etc/porelo-host/projects` exists,
    then runs the block that asks `porelo-host project give-back-check` and includes `people`. It reads the follow's
    units and stops the timer and service, waiting for an active follow. It asks the same block again; on a refusal
    it starts the timer again and fails with the refusal's text. The block stays one YAML anchor inside that file.
  - A variable `porelo_host_give_back_people` (default `true`) lets the forge's uninstall ask only for the work at
    central, since people stay on a host that keeps running. That uninstall, planned in the issue that installs and uninstalls the forge and Matrix alone, calls
    this file instead of keeping a copy.
- **`porelo-host-measure`:** `main` keeps `argparse`, the `--raise` rule and the mapping, and calls one
  `measure(options, machine)`. That function holds the given labels' rule, the obstruction, the result file's
  checks, the signal handlers, the lock under `/run` and the publication by `link(2)`. `main` maps its exception to
  exit 2 as now.
- **Red first:** a unit test calling `measure` with a lock already present answers 1, leaves the lock and publishes
  nothing. It fails today because `measure` does not exist; the break is seen by removing the lock check once. A
  `tests/unit/roles` test reading `playbooks/down.yml` fails on any task that is not an inventory assert or a role
  call: the harm guarded is a refusal path that lives only in the playbook and so is not shared with the forge's
  uninstall.
- The Molecule scenario `default`, whose side effect runs `down`, stays green unchanged. That shows the moved check
  behaves as before, the refusal with the follow resumed included.

## Acceptance

- The new unit test, seen red first, the unit suite, sanity and the Molecule `default` scenario green.
- `down.yml` holds no task but its inventory asserts and role calls.
