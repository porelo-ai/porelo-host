# HO150 — The Forge Role's JDK Fetch Tries Again By The Pinned Rule

**Status:** Review.
**Size:** XS - one task in `roles/forge/tasks/runner.yml`, its pattern in the role's vars, a unit test and the Molecule
job's time.

**What must be true.** The forge role's fetch of the runner's pinned JDK tries again on what waiting may mend, a 5xx or
no answer, within the 15 minutes of the pinned downloads' rule, and fails at once on a 4xx, a refused certificate or a
wrong digest.

## Why

On 2026-11-08 GitHub's release downloads answered 504 and timed out for over ten minutes. porelo-buildtools' pinned
downloads now try again by one rule. The forge role fetches the runner's JDK, a Temurin release asset on
GitHub, with `get_url` once, with its default timeout of 10 s. In the Build of `0f7993b` the Molecule scenario with the
forge failed there: "Connection failure: The read operation timed out", and a host's first up would have failed the
same way.

## The shape

- `get_url` with `timeout: 60`, `retries: 7`, `delay: 120`: eight attempts, 14 minutes of pauses. Ansible's pause is
  fixed, so the rule's doubling pauses are not copied; its budget is.
- `until` holds, so the task ends, on success or on a failure that waiting will not mend. It tries again only on:
  - a `status_code` of 500 or more;
  - no `status_code` and a message of `get_url` for no answer: "Connection failure: ", "Request failed: <urlopen error "
    or "Incomplete read";
  - or a break while the body streams, which `get_url` words "failed to create temporary content file: " and the
    network's error: a timeout, a reset or aborted connection, a broken pipe, an `IncompleteRead` or `EOF`. A full
    disk or a refused permission there is not tried again.

  These are named in `__forge_runner_jdk_fetch_unanswered`.

  A refused certificate (`CERTIFICATE_VERIFY_FAILED`) is a "Request failed: <urlopen error" too, and is not tried
  again.
- The Molecule job's `timeout-minutes` goes from 45 to 60, so it is not stopped while the fetch still waits.

## Reading

Read once by agy `gemini-4-argon-high` (839 s), with three findings:
1. A body that times out or breaks off while it streams was not retried. It is now, with four cases in the test, and
   a full disk and a refused permission stay refused.
2. A cited issue of another repository. The words now say what that repository does instead.
3. The changelog entry was missing. It is now under *Fixed*.

## Tests

`tests/unit/roles/test_forge_runner_jdk_fetch.py`, red against the task before:
- the task's budget: 15 minutes, with a 60 s timeout;
- its `until`, evaluated with Ansible's `succeeded` and `regex` tests, tries again on:
  - a timeout, an unresolved name and a broken read;
  - a 504 and a 502;
- and stops at once on:
  - a success;
  - a 404 and a 403;
  - a wrong digest;
  - a refused certificate;
  - an unwritable destination.

The same seven cases were also evaluated by `ansible-playbook` in the tools image, with the same answers.
