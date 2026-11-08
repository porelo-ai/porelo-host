# HO148 — The Move Check Finds The Push By Its Branch And Names The Answer

**Status:** Review.
**Size:** XS - one script, `build/move-check.sh`, and its unit tests.

**What must be true.** The move check finds a task's push and pull request in the repository of the host's forge that
holds the task's branch, fails the Build line where the reader sees no `builds:`, and every failing line says what the
forge, Git or the vault answered, so a refused token, a missing scope and a missing repository read apart.

## Why

On a move's host the check asked the forge for the repository's key in `project.yml` (`pi`), while the forge holds it
under its central name (`porelo-pi`), so the push and the pull request failed on a move that had gone right. It took
the build reader's "not configured" as a pass, although the host names `builds:` for every project on its forge. Its
failing lines said only that a reader failed, which left a refused token and a missing repository looking alike.

## Plan

- The repositories come from the forge's `GET /orgs/<project>/repos`, with the person's vault answering for the
  token as before; the one that holds `porelo/<task>` or `porelo/<task>-<n>` is the push's, and none or several fail
  with their names. The build reader keeps the task's key.
- Exit 78 of `porelo build status` fails the Build line.
- `api()` keeps the HTTP status: a line says `HTTP <code> for <path>`, the vault's refusal and Git's `fatal:` line by
  their own words; no token or header reaches a line.
- **Red first** in `tests/unit/test_move_tools.py`: the push found under the central name, a branch in two
  repositories, an invalid repository list, 78 failing, and a 401, a 403, a vault without the entry and Git's refusal
  each named; a pull request reader that fails alone, a later repository Git cannot read, and a `HEAD` naming the
  task's branch. The temporary file for Git's answers goes on a signal too, as dash runs no `EXIT` trap on one.

## Acceptance

- The unit tests, seen red on today's script.
- On the next move's host, C15 shows the push and the pull request of a task as `ok`.
