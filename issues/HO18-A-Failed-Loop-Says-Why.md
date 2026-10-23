# HO18 — A Failed Loop Says Why

**Status:** Accepted.

**What must be true.** When a task that loops over items fails, the line `porelo.host.lines` writes for it carries what
failed and why, in the failing command's own words, as a single task's failure does; a task with `no_log` still writes
nothing of its output.

## To be checked

- **What a loop's result holds:** the callback writes the result's `msg`, which for a loop is only "One or more items
  failed"; the items' `rc`, `stderr` and `msg` sit under `results`. Seen at a `porelo task start` that ended 69: the
  line said nothing of Porelo's refusal, which Ansible's own output showed.
- **What may be printed:** whether an item's `stderr` can carry a secret where its task has no `no_log`, and how the
  callback tells an item's `no_log` from the task's.
