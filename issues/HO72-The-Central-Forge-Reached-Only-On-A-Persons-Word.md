# HO72 — The Central Forge Reached Only On A Person's Word

**Status:** Implementing.
**Size:** M - the migration moves out of bring into a helper verb, and the project removal's check takes the token from
its caller; measured M median 63 min, from three M builds (47, 63, 75).

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** No token for the central forge lies on the host, unless a project opts in, which is a later
issue.

- The bring's migration of a project's repositories, the gathered push and the pull of the central state take the
  starting person's own token on standard input through the tunnel and use it once, through a credential helper reading
  a pipe: never in a process's argv, a log, a file or `.git/config`.
- The publisher's and the runner's own tokens, which act only on the host's forge, stay.
- Goes: the `forge-central-token` stop and `/run/porelo-host/forge-central.token`.

## Acceptance

- after each of the three, the token is in no file, no `.git/config` and no log, and was in no argv (a test watching
  `/proc/*/cmdline`).

## Plan

- `roles/forge/tasks/repositories.yml` migrates no more inside bring: the stop and the token file go. A new verb
  `porelo-host-project migrate <project>` (`roles/forge/files/porelo-host-project`), run by the project admin's Porelo
  through the tunnel, reads the central token from stdin, migrates the repositories the verified project names that the
  forge lacks, and keeps the token in memory alone; `credential.helper` is a pipe-reading shell function, never `argv`
  or `.git/config`.
- `porelo-host-project remove`'s check (`central_forge_token()`, line 501) takes the token from its caller's stdin
  instead of `/run/porelo-host/forge-central.token`; `porelo-host-push` already reads it from stdin.
- The pull of the central state: `porelo-host-push --pull <project>` with the same stdin token, fast-forwarding the
  host's `main` from the central one.
- Goes: `forge-central-token` in `porelo-host-stop`, `doc/lines.md`, the bring's `__forge_central_token` vars in
  `tasks/own.yml`.
- Red first: unit tests for `migrate` and `--pull` with a stand-in forge, asserting the token is in no argv
  (`/proc/*/cmdline` sampled by the stand-in), no file and no output.

## To be checked

- Forgejo's migrate API takes the token in the JSON body (`auth_token`); that the body never reaches a log.
