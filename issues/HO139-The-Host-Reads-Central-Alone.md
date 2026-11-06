# HO139 — The Host Reads Central Alone

**Status:** Review.
**Size:** XS - one helper's reading of the verified project file, its unit tests and the documentation.

**What must be true.** The host reads a repository of the project file by its name and its `central` address alone. A
host's address never stands in the project file: the host derives its own forge for what it carries, and what it does
not carry works against `central` directly. Porelo's `porelo project verify` refuses the retired key `upstream`, which
named the local forge; that is porelo's part.

## Why

On the rehearsal's host (operator, 2026-11-06) the move wrote `upstream: http://127.0.0.1:3001/...` into the signed
project file, a detail of one host that changes with every host the project is put on. The operator decided the
project file names only the central forge.

## Plan

- `project_file_values` in `roles/porelo/files/porelo-host-person` keeps a row's `review` and `central`, and no
  `upstream`.
- `no_task_in_own` knows the project's own repository by a row's central address, not by `upstream`.
- `doc/local-forge.md` says the project file names each repository's `central` and no host, and how the host derives
  its forge's address.
- `build/move-check.sh` no longer points at a `builds:` block as the way to a pushed commit.
- **Red first:** a row whose `upstream` names the project's own repository leaves it closed.

## Acceptance

- Unit tests seen red on the reading by `upstream`, green after; the full suite, black, ansible-lint and the document
  checks pass.

## Done

- `project_file_values` keeps `review` and `central` alone; `no_task_in_own` knows the project's own repository by a
  row's central address alone, whatever the file calls the row. **Changed after the reading (agy, gemini-4-argon-high):**
  the first cut still took a row named like the project, with no central address or another one, for the project's
  repository and left it open to merges.
- Unit tests: a row whose `upstream` names the project's own repository leaves it closed, to merges and to the copy's
  advance, and is not kept in the host's record (red on the reading by `upstream`); so do a row named like the project
  with no central address or another one (red on the first cut).
- `doc/local-forge.md`: the project file names `central` and no host; the host derives `http://127.0.0.1:<git_port>/
  <project>/<name>.git` for what it carries. The move check's text no longer names `builds:`.
- **Not changed:** the move check still reads porelo's exit 78 of the build reader as "not configured", which is
  porelo's answer for a project without a build reader.
