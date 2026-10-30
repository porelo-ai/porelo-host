# HO72 — The Central Forge Reached Only On A Person's Word

**Status:** Accepted (operator, 2026-10-30, with the project's one-click joining).
**Size:** M - the migration, the gathered push and the pull changed to a token on stdin, with unit tests and a VM run;
measured M median 63 min, from three M builds (47, 63, 75).

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** No token for the central forge lies on the host, unless a project opts in, which is a later
issue.

- The bring's migration of a project's repositories, the gathered push and the pull of the central state take the
  starting person's own token on standard input through the tunnel and use it once, through a credential helper reading
  a pipe: never in a process's argv, a log, a file or `.git/config`.
- The publisher's and the runner's own tokens, which act only on the host's forge, stay.
- Goes: the `forge-central-token` stop and `/run/porelo-host/forge-central.token`.

## Tests

- after each of the three, the token is in no file, no `.git/config` and no log, and was in no argv (a test watching
  `/proc/*/cmdline`).
