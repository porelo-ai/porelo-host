# HO127 — The Half For Jobs Is A Setting

```json
{
  "$schema": "issue-1.json",
  "id": "HO127",
  "title": "The Half For Jobs Is A Setting",
  "state": "Review",
  "size": "S",
  "priority": "Medium",
  "rank": 1,
  "blockedBy": [],
  "covers": "The share of the host for jobs and the VM pool becomes a setting, today's half its default, `up`'s refusal naming it."
}
```

**Why this size.** one setting read in two roles and the check's fit, with their tests and docs; no contract another
repository reads changes.

**What must be true.** The share of the host that jobs and the VM pool may take is a setting, with today's half as its
default. `up`'s refusal names the setting. Setting it above the half is an operator's choice and `up` warns of it, as this limit
protects nothing but the host's own work.

**What is known.**

- `forge_runner_capacity`, `forge_job_cpus` and `forge_job_memory` move the jobs only within the half, which cannot be set.
- The half stands in two places: `roles/forge/tasks/capacity.yml`, for processors and for memory together with the pool, and
  `roles/vm_pool/tasks/memory.yml`, for the pool alone. Both must read the one setting, and `doc/machines.md` and both roles'
  READMEs say the half.
- [HO125](README.md#ho125) measures past the half on purpose and needs a way to get there; this is it. What default the
  numbers support is its answer, not this issue's.

**Acceptance.** Unset, the same refusal at the same size as today, naming the setting. Set above the half, an `up` that fits it,
with its warning in the output. Set beyond the whole host, a refusal. A unit test or the capacity entry point shows each.

## Plan

- **The setting:** `porelo_host_work_share`, collection-wide like the other `porelo_host_*`, the percent of the host's
  processors and memory the forge's jobs and the VM pool may take together; unset 50, today's half. A whole number from
  1 to 100; anything else, beyond the whole host among it, is refused before anything changes.
- **The check's fit** (`roles/check/files/porelo-host-check --fit`) takes `share_percent` in its request; unset, the
  limits' `host_share_divisor` as today, so an older caller gets the same answer. `cpus * percent // 100` and `kib *
  percent // 100` equal today's `// 2` at 50.
- **`roles/forge/tasks/capacity.yml`** hands the setting to the fit and names it in its refusal;
  **`roles/vm_pool/tasks/memory.yml`** checks the pool against the same share and names it. Above 50, `up` writes a note
  (`porelo_host_note`): the host's own work, Forgejo, the runner and the tasks, keeps less than half.
- **Docs:** `doc/machines.md`, `doc/index.md`, both roles' READMEs and argument specs say the share and its setting.
- **Red first:** the check's fit at 75 accepts what it refuses at 50; the same request at 101 is refused; unset, today's
  answer and a refusal naming `porelo_host_work_share`; the pool's assertion and the note read from the role files.

## Checked

- Molecule on the test host (forge on, pool off, 2026-11-10): syntax, converge, idempotence, verify and side effect
  pass with the setting unset; the unit tests cover the share set to 75 and 101 and the pool against it.
