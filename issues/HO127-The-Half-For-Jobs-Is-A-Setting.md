# HO127 — The Half For Jobs Is A Setting

**Status:** Backlog, by the operator's word. After the test.

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
