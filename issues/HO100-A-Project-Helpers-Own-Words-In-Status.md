# HO100 — A Project Helper's Own Words In Status

**Status:** Review.
**Size:** S - one helper's refusal path and its tests, no contract other repositories read.

**What must be true.** When the project helper refuses, `org status` gives that project's `why` in the helper's own
words, as a person can do nothing with `the project helper migrate exited 65`. The words also reach the journal.

## Plan

- `follow_project_command` in `porelo-host-person` takes the last line of the helper's captured error output, only when
  it carries the helper's own `porelo-host-project: ` prefix, bounded and with control characters removed. Its exit code
  stands beside it; the refusal's own code stays 69, as 65 and 78 mean something else to the follow.
- Anything else keeps today's sentence: no line, a line that is not the helper's, or a line holding the supplied token.
- The words go to standard error too, so the follow's journal has them.
- Red first in `test_porelo_host_person_follow.py`: a refused migration's words stand in `why`, and a token in the
  helper's other output or in its last line does not.

## Acceptance

- `org status` shows the helper's refusal and its exit code, the journal shows the same, and no supplied token reaches
  either, seen failing with the filter broken on purpose.
