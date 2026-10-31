# HO80 — Git And The API On The Host's Loopback With A Token

**Status:** Review (Backlog: operator, 2026-10-31), the middle way for [HO69](README.md#ho69).
**Size:** M.

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** Git, the API and a task's pass-on reach the host's forge at `http://127.0.0.1:<git_port>` with
a token, through the same token-only gate `git.sock` is. Forgejo itself never listens on TCP. The browser keeps
`web.sock`. No root verb exists only because Git cannot speak to a Unix socket.

## Analysis

**The endpoint.** `porelo-forge-git.socket` gets a second `ListenStream=127.0.0.1:<git_port>` beside `git.sock`, with
`Accept=yes` as now. The gate's git mode already does the following, and does it the same on TCP:

- it never sets a user header;
- it drops every `X-WEBAUTH-*` and `Cookie`;
- it answers 401 Basic to a request without `Authorization`;
- it passes only `Basic|token` on to Forgejo's own Unix socket.

The gate reads `SO_PEERCRED` for every connection; on TCP Linux answers `(0, -1, -1)` (measured), which git mode never
uses. The web mode stays on `web.sock` alone, since it trusts the peer's uid.

**1. What goes, and what stays.**

- **Goes:**
  - from `roles/forge/files/porelo-host-push` (695 lines), the private network namespace per Git transfer: the
    `unshare --net` Python forwarder, its clean-up watcher and the coproc's token handshake;
  - from `tests/unit/roles/test_porelo_host_push.py` (1436 lines, 42 tests), most of the namespace, forwarder and
    signal tests;
  - the held `--task` verb, entirely;
  - sudo for `--pull` and for the gathered push: both can run in the person's own account, as `--migrate` already
    does, with the person's token from `sudo -n porelo-host-person forge-token` and the central token on stdin;
  - the `porelo-people` sudoers rule for `porelo-host-push`.
- **Stays:**
  - root's `--check` before project removal, run by `porelo-host-project` as root, now over TCP without a namespace;
  - `curl --unix-socket` in the roles: those calls go to Forgejo's own `http.sock` as root, not through the gate;
  - `web.sock` and its `SO_PEERCRED` sign-in;
  - the runner gate and its socket proxy. Jobs share the proxy's network namespace (`container:forgejo-runner-proxy`),
    where `127.0.0.1:<git_port>` is the proxy's own `socat` to `runner.sock`. They never see the host's loopback.
  - the person's forge token, made by the host on demand;
  - the task's token held by the gate.

**2. For Agent Core.** The task's pass-on through the gate becomes a plain `git push http://127.0.0.1:<git_port>/<project>/<repo>.git
porelo/<task>`. The task token comes from the vault to Git through a credential helper on stdin, never in the URL;
`HostPush` is the one place it changes (an S, as Core said at 04:39Z). The sudo call and the record and owner checks
of `--task` go, because the forge checks the token and its scopes itself. The principal check at the task's start
stays.

**3. Who reaches the port.**

- Every process on the host: every login, the host admins, the service accounts (`porelo-forge`, `porelo-runner`,
  `porelo-matrix`) and any daemon. Today `git.sock` (`porelo-people`, 0660) keeps out every account that is not a
  person or the forge.
- In both cases the token is the real bound: with no token, a connection gets 401 and nothing else.
- Narrowing it is possible with an nftables `output` rule on `127.0.0.1:<git_port>` by `meta skuid`, for a set of
  uids the person helper keeps (persons and the forge account). It is optional, and S on top.
- A rootless container with pasta's defaults does not reach the host's loopback. Measured on this workstation (podman
  5.7.0, pasta 2026-01-20): `127.0.0.1`, `host.containers.internal` and `169.254.1.2` were each refused while a
  listener answered on the host's `127.0.0.1`.
- To be measured on walk6m after today's test: the same, and a Porelo task's container with the network Porelo
  gives it (Agent Core's container hardening).
- `--network host` or `pasta --map-host-loopback` would reach the port; neither must be used for a task or a job.

**4. What Forgejo shows there without a token: nothing.** The gate answers 401 before Forgejo sees the request. The
pre-auth surface is the gate's own parser (Python's `http.server` with its header, length and chunk checks): the same
surface `git.sock` has today, now open to every local uid, not only to `porelo-people`. With a token, Forgejo answers
within the token's scopes. Brute force of a 40-hex token is no attack.

**5. Recommendation, size, and today's test.**

- **Recommendation:** take the middle way.
  - It removes the namespace per transfer, the sudo push and pull, and the `--task` verb: three root surfaces the
    socket-only design added only because Git has no Unix-socket transport.
  - It keeps the property that matters: no password, and no anonymous access. The browser keeps its peer-checked
    socket, and Forgejo is never on TCP.
  - What it gives up is the socket's file permission as a second bound in front of the token. The nftables rule
    can restore it.
- **Size:** M.
  - The socket unit and the gate's TCP case.
  - `porelo-host-push` reduced to person-run push, pull and migrate, plus root's `--check`.
  - The sudoers rule removed.
  - [HO69](README.md#ho69)'s, [HO72](README.md#ho72)'s and [HO75](README.md#ho75)'s texts, the guide, and the
    tests, including Molecule's `push.yml`.
- **Today's test:** none. The 07:00 run on walk6m tests today's state. After michi's decision, the steps file's
  push and pull steps lose their `sudo -n`, and Group 3's pass-on is run again with Core's swapped `HostPush`.

## Plan

- `porelo-forge-git.socket` listens on `127.0.0.1:<git_port>` beside `git.sock`, `Accept=yes` as before. The gate
  reads `SO_PEERCRED` only on a Unix socket; its web and runner modes refuse any other connection before reading it.
- `porelo-host-push`: push, `--pull` and `--migrate` run in the person's own account and refuse root with 77. Each
  gets the local token through `sudo -n porelo-host-person forge-token`, which refuses a locked person or one no
  project holds. Local Git takes the token as a header in its environment, as central Git does, with no CA. Root's
  `--check` stays, now over TCP. The namespace, its forwarder and clean-up watcher, the credential pipe, the reading
  of the person record and the reading of the config as the caller go.
- The sudoers rule goes; `up` removes it from a host that has it, and `down` still removes it. `porelo-host-person
  forge-token --for`, which only the sudo push used, goes.
- `--task` was never pushed, so nothing of it is in this change.
- Texts: [HO69](README.md#ho69) and [HO72](README.md#ho72), the forge role's README, `doc/local-forge.md`,
  `doc/lines.md`, the changelog. The host guide already had the push in the person's own account.

## Tests

- `tests/unit/roles/test_forge_gate.py`: on an accepted loopback TCP connection, git mode answers `401` with
  `WWW-Authenticate: Basic`; web and runner modes refuse it with no answer (both red against the old gate).
- `tests/unit/roles/test_porelo_host_push.py`: every push, pull and migration runs as the person with the token from
  `sudo -n porelo-host-person forge-token`; root is refused with 77; local Git gets the token as a Basic header and no
  CA; the socket unit has both listeners; no sudoers file, its removal in `up` and `down`, and no `unshare` remain.
  The namespace, forwarder, sudo-caller, person-record and credential-pipe tests are removed with their code.
- `tests/unit/roles/test_porelo_host_person_tasks.py`: `forge-token --for` is refused as an unknown call, as root and
  through sudo.

## Not built here

- Molecule's `push.yml` is still the VPN scenario throughout (WireGuard keys, `10.73.7.1`, identity token files). It is
  rewritten with the rest of Molecule in [HO74](README.md#ho74), not here.

## Acceptance

- [ ] On a host after `up`: `ss -ltn` shows `127.0.0.1:<git_port>` held by systemd, and nothing of Forgejo's on TCP.
- [ ] `curl -sI http://127.0.0.1:<git_port>/` answers `401` with `WWW-Authenticate: Basic`.
- [ ] A person's `porelo-host-push <project>` without sudo pushes local `main`; `--pull` brings `central/main`.
- [ ] `/etc/sudoers.d/porelo-host-push` is gone after `up` on a host that had it.
- [ ] The walk6m measurement below.

## Idea part, not built now

- The nftables `output` rule on `127.0.0.1:<git_port>` by `meta skuid`, for the persons' and the forge's uids, which
  narrows the port to the circle `git.sock` has today (operator, 2026-10-31).

## Open questions

- The walk6m measurement of a task's container.
