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
  `porelo-host-push` reads it from stdin; central git gets it as a header in its environment, never `argv` or config.
- The pull of the central state: `sudo -n porelo-host-push --pull <project> [repositories...]` takes the stdin token
  and brings central `main` to the local forge as `central/main`; local `main` reaches it by a pull request.
- Goes: the token file in `porelo-host-stop`, `doc/lines.md` and `doc/local-forge.md`, the bring's
  `__forge_central_token` vars in `tasks/own.yml` and `down.yml`.
- Red first: unit tests for `--migrate` and `--pull` with a stand-in forge, asserting the token is in no argv
  (`/proc/*/cmdline` sampled while they run), no file and no output; the stop's tests assert the pipe.

- Push and pull move to sudo: `sudo -n /usr/local/sbin/porelo-host-push [--pull] <project> [repositories...]` validates
  `SUDO_UID` and `SUDO_USER`, current developer or project-admin membership, and the caller's private config as before.
  Root reads that config as the caller after checking it, so a raced path cannot expose root-only files.
  The checked `porelo-people` sudoers rule admits the helper, which validates every argument. Root calls
  `porelo-host-person forge-token --for <login>` with no sudo caller; that new form is root-only. Migration stays in the
  person's account and obtains its local token through `sudo -n porelo-host-person forge-token`.
- Local APIs use `curl --unix-socket /run/porelo-forge/git.sock http://localhost/api/v1/...`, token header on a pipe.
  Every local Git clone, fetch, push and check runs as root under `unshare --net`, bringing up loopback and starting a
  Python 3 isolated standard-library forwarder at `127.0.0.1:<git_port>` to `git.sock` inside that namespace alone.
  Git has no HTTP-over-Unix-socket transport, and Ubuntu 26.04 refuses unprivileged user namespaces. Git gets its
  local token through a credential helper reading a pipe/fd; central HTTPS and CA behavior stay the same.
- Red first: socket API, namespace setup and failure, credential fd, sudo caller and membership, root-only named
  token calls, and sudoers rule tests. Update the push config writers, teardown, local-forge guide, lines and role
  README. The migration pipe accepts a token ending at EOF, as the stop's base64 decoder produces it.

## To be checked

- Push and pull have moved to sudo; run installed-host acceptance for both, root's check, and person-run migration.
  Observe namespace isolation, socket forwarding, credential handling, interrupt cleanup and no host TCP listener.
- Run the pinned lint, document checks and full workflow outside the sandbox; podman cannot start here. Obtain the
  required independent model review. Plain touched-file unit tests exercise namespace creation through stubs only.

- Forgejo's migrate API takes the token in the JSON body (`auth_token`); that the body never reaches a log.
- Forgejo's migration of a `git` service may put the token into the clone URL of its own `git clone`, so it would stand
  in an argv other accounts read through `/proc`, and in the clone's config while it runs (reading of cb52be0). To be
  measured on the pinned Forgejo; if so, either `/proc` is mounted `hidepid=invisible` or the migration clones with
  git's own header and creates the repository empty, keeping the central address beside it.
