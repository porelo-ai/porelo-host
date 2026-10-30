# HO72 — The Central Forge Reached Only On A Person's Word

**Status:** Implementing.
**Size:** M - the migration moves out of bring into a helper verb, and the project removal's check takes the token from
its caller; measured M median 63 min, from three M builds (47, 63, 75).

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** No token for the central forge lies on the host, unless a project opts in, which is a later
issue.

- The bring's migration of a project's repositories, the gathered push and the pull of the central state take the
  starting person's own token on standard input through the tunnel and use it once, on a pipe or in git's own
  environment: never in a process's argv, a log, a file or `.git/config`.
- The publisher's and the runner's own tokens, which act only on the host's forge, stay.
- Goes: `/run/porelo-host/forge-central.token`; the `forge-central-token` stop stays, and pipes the token instead.

## Acceptance

- after each of the three, the token is in no file, no `.git/config` and no log, and was in no argv (a test watching
  `/proc/*/cmdline`).

## Plan

- `roles/forge/tasks/repositories.yml` migrates no more inside bring: where a repository is still to migrate, it lists
  them in `~/.config/porelo-host/push/<project>.migrate` (the push config's form, no secret) and waits with the need
  `forge-central-token`, unchanged for the interface. The token file goes.
- The person's stop (`porelo-host-stop --stdin forge-central-token`) pipes the token into
  `porelo-host-push --migrate <project>` in the person's own account, which checks the list like a push config, has
  Forgejo migrate each listed repository it lacks with the person's own forge token, the central token in the request
  body on a pipe alone, and removes the list; the bring run again goes on. The migration sits beside the push rather
  than in `porelo-host-project`, which is root's alone and would need a new sudo rule.
- `porelo-host-project remove`'s check (`central_forge_token()`) already takes the token from its caller's stdin, and
  `porelo-host-push` reads it from stdin; git gets it as a header in its environment, never `argv` or `.git/config`.
- The pull of the central state: `porelo-host-push --pull <project> [repositories...]` with the same stdin token brings
  central `main` to the local forge as `central/main`, since local `main` is protected and reaches it by a pull request.
- Goes: the token file in `porelo-host-stop`, `doc/lines.md` and `doc/local-forge.md`, the bring's
  `__forge_central_token` vars in `tasks/own.yml` and `down.yml`.
- Red first: unit tests for `--migrate` and `--pull` with a stand-in forge, asserting the token is in no argv
  (`/proc/*/cmdline` sampled while they run), no file and no output; the stop's tests assert the pipe.

## To be checked

- Forgejo's migrate API takes the token in the JSON body (`auth_token`); that the body never reaches a log.
- Forgejo's migration of a `git` service may put the token into the clone URL of its own `git clone`, so it would stand
  in an argv other accounts read through `/proc`, and in the clone's config while it runs (reading of cb52be0). To be
  measured on the pinned Forgejo; if so, either `/proc` is mounted `hidepid=invisible` or the migration clones with
  git's own header and creates the repository empty, keeping the central address beside it.
