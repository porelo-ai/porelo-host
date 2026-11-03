# HO100 — A Project Helper's Own Words In Status

**Status:** Idea.

**What must be true.** When the project helper refuses, `org status` gives that project's `why` in the helper's own
words, as a person can do nothing with `the project helper migrate exited 65`. The words also reach the journal.

**Plan.** `follow_project_command` takes the helper's refusal line from its captured error output: the last line only,
bounded and with control characters removed, its exit code kept beside it; a helper that said nothing keeps today's
sentence. A test holds that a refused migration's words stand in `why`, and that a token in the helper's other output
does not.
