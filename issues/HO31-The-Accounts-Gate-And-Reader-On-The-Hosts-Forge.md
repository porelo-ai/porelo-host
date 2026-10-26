# HO31 — The Account's Gate And Reader On The Host's Forge

**Status:** Backlog; blocked by [HO29](README.md#ho29), since only the person's own forge login can approve a pull
request.
**Size:** M - task files in the roles `forge` and `porelo`, a credential handed into the vault, the protection of
`main`, a contract with porelo-project on the vault entry's name, and Molecule's checks reworked around a protected
`main`.

Analyzed for porelo-project [PJ61](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj61)'s
sprint 5, for porelo-message-sluice.

**What must be true.** On a host whose project names the local forge as its upstream, the gate of Porelo's account
pushes `porelo/<task>` to the forge by its name over TLS. The `forgejo` build reader reads that branch's verdict and
logs. Neither the gate nor any task can push to `main`, which only the person's approved and merged pull request
reaches. The forge's token for the gate and the reader is in the account's vault alone.

## Plan

- **The forge's name on the host:** `/etc/hosts` gains `127.0.0.1 forge.porelo.internal` between markers
  (`ansible.builtin.blockinfile`, role `forge`, `tls.yml`), since the forge's HTTPS socket listens on `127.0.0.1:443`
  and its certificate names `forge_name`. `down.yml` takes the block out. The host's `git` trusts the forge through
  the account's `ca-certificates.pem`, which the role `porelo`'s `trust.yml` already writes and porelo
  [B286](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b286) passes as `GIT_SSL_CAINFO`; the
  reader reads the same file, as porelo-adapters documents.
- **The build reader:** the role `porelo`'s `install.yml` installs `porelo-adapter-forgejo` from Porelo's repository
  where `porelo_host_forge` is true. It provides `/usr/libexec/porelo/builds/forgejo`.
- **The account's forge identity:** `roles/forge/tasks/gate.yml`, after `person.yml`, where the organization exists
  (`forge_repositories` not empty, as for `repositories.yml`). Its own variable
  `forge_porelo_account` takes `porelo_host_account`; it does not touch the facts the role `porelo` reads later.
  - A Forgejo user `porelo-<account>` is made by Forgejo's command line, in a team `gates` that writes code and pull
    requests and reads Actions, on every repository of the organization.
  - Its token (`write:repository`, and the scopes the reader needs) carries a token name of its own and is made only
    while the account's vault lacks the entry.
- **Into the vault, by Porelo alone:** Forgejo's container prints the token, and the shell pipes it straight into
  `porelo vault put git.token.forge.porelo.internal`, run as Porelo's account, which reads standard input, as Molecule
  already does for a key. The token is never a variable, a register or a file, and the task carries `no_log`. The
  entry's name is the default both porelo's gate and the `forgejo` reader fall back to for that host
  (`git.token.<host>`), and porelo-project's `project.yml` names no `builds.credential`, so one token serves both.
- **`main` protected**, `roles/forge/tasks/protection.yml`, after `gate.yml`, on every repository of
  `porelo_host_forge_repositories`, through the admin's API (`branch_protections`):
  - pushes are refused for everybody;
  - one approval is required, and approvals and merges are allowed for the person's account alone;
  - status checks are not required, since the person reads the build.
- **porelo-message-sluice seeded:** as today, by `porelo_host_forge_repositories` in the forge's inventory.
- **Molecule around a protected `main`:** `tasks/forge_push.yml` commits B to `porelo/stand-in` on a branch and lets
  `operator` approve and merge its pull request, in place of the direct commit to `main` it makes today.
- **`doc/local-forge.md`** names the gate's account, the vault entry and the protection, in place of "Configure
  protection before relying on this acceptance boundary".

## Acceptance

- In Molecule's verify:
  - with the gate's token, taken from the vault on a pipe, a push of `main` is refused and one of `porelo/probe` is
    taken;
  - `git ls-remote https://forge.porelo.internal/porelo/stand-in.git` as Porelo's account answers;
  - a pull request merged without the person's approval is refused, and the person's approved one reaches `main`;
  - `/usr/libexec/porelo/builds/forgejo` reads the verdict of the probe branch's run through `forge.porelo.internal`
    with the vault's token;
  - `porelo vault list` names the entry, and the token's digest is in no `-vvv` output, journal line or task container.
    The entry is removed before the `-vvv` `up`, so that run makes it again.
  - after `down`, the `/etc/hosts` block is gone.
- Each is seen red without its task file.

## To be checked

- How Molecule takes the token back out of the vault for its checks, on a pipe and never on a command line.
- Which token scopes the `forgejo` reader needs for a job's log: an agent's token with Actions read got `404` for a
  log through the API.
- That Forgejo 17's branch protection allows a merge by the approvals' whitelist while pushes are off.
