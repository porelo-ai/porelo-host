# HO18 — A Failed Loop Says Why

**Status:** Review.
**Size:** S - one callback, real-playbook regression tests, and its message contract documentation.

**What must be true.** When a step fails, the line `porelo.host.lines` writes for it carries why, in the failing
command's own words, and for a loop each failed item's by its label; a task or item with `no_log` still writes nothing
of its output.

## Plan

- In `plugins/callback/lines.py`, keep the waiting line's raw message parsing and enrich only failure messages with
  stderr, else stdout, and labeled failed loop items. Check hiding markers before reading message details, never
  read exception text or command metadata, preserve output tails, and cap the complete message at 4000 characters.
- Add real-playbook cases in `tests/unit/plugins/callback/test_lines.py` and `plays/`: loop stderr and label,
  single stdout, long output tail, task-level and item-level hiding, and omitted-item counts. The diagnostic cases
  build planted words at run time so command metadata cannot satisfy them. Run hiding cases with traceback
  enabled and include a hidden fail-module loop so the callback must not read exception text. Guard per-item
  failed_when, single-result caps, stderr tails, and oversized loop labels and messages.
- Describe the message in `doc/lines.md`, add the changelog entry, and correct the migration comment in
  `roles/forge/tasks/repositories.yml`; keep its aggregate assertion to stop once with every repository's answer
  named, since Ansible already runs every loop item even when one fails.

## Acceptance

- Real `ansible-playbook` output includes the failed command's reason and loop label, preserves a long output's
  tail, stays within the message cap, and counts omitted failures.
- Hidden task and item output appears nowhere in the complete run output, and the failed message says hidden.
- The pinned-image unit suite and workflow checks pass; the contract version stays 1.

## Built

- `lines.py` adds to a failed line's `msg`, after Ansible's words, the command's stderr, else its stdout, cut to its
  last 1000 characters, and for a loop each failed item's by its label, each entry at most 1000 characters; the whole
  `msg` is at most 4000 characters, Ansible's words cut before the command's, naming how many items it left out. A
  loop item carries no `failed` key in ansible-core 2.21: its `failed_when_result`, else its `rc` or an
  `exception`'s presence, says it failed. Ansible censors a `no_log` task's result and every item of it before the
  callback sees it; the callback says hidden and reads only whether `exception` is there, never its text.
- Seen red first: against the unchanged callback the tests of a loop's reason, a command's reason on stdout, a reason
  at the end of 20 KB and dropped items counted failed; the `no_log` tests passed, Ansible censoring already, and their
  search found the planted value in a copy of the play without `no_log`. With the change 28 passed, `black` clean.
  Each of seven breaks of `lines.py` turned at least one test red: `failed_when` ignored, the single step uncapped,
  the head kept for the tail, `exception`'s text printed, a loop entry uncut, `cmd` printed for the words, every item
  read as not failed.
- **Declined:** a test for the callback's own `no_log` check on the whole result. Removing it stays green, since
  Ansible hands a `no_log` task's result over censored and the item branch then says hidden; a test would need a result
  Ansible never produces, which a fixture may not state.
- Read against `ansible-good-practices` and `ansible-new-collection`, each `2026.824.2`, by agy
  `claude-opus-5-5-high`; its findings on the tests are fixed above.
