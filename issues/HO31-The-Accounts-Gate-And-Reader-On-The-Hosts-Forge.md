# HO31 — The Account's Gate And Reader On The Host's Forge

**Status:** Implementing.
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
  entry's name is the gate's `git.token.<host>` name. The build configuration must explicitly name
  `builds.credential: git.token.forge.porelo.internal`, so one token serves both.
- **`main` protected**, `roles/forge/tasks/protection.yml`, after `gate.yml`, on every repository of
  `porelo_host_forge_repositories`, through the admin's API (`branch_protections`):
  - pushes are refused for everybody;
  - one approval is required, and approvals and merges are allowed for the person's account alone;
  - status checks are not required, since the person reads the build.
  - the person cannot approve a pull request they opened, so another forge account opens it: the gate's identity,
    whose team writes pull requests, once porelo
    [B297](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b297) is built, and an agent's account
    until then. Found in sprint 5's test, where the person's own pull request could not be approved.
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

- Run the full pinned-image workflow and Molecule on a VM; the implementation environment allows no network,
  installation, podman or Molecule. Static checks cannot prove the runtime acceptance criteria.
- Verify the project's build configuration names `builds.credential: git.token.forge.porelo.internal`; the locally
  available Porelo parser requires it and has no default for the reader. This repository changes no project file in
  another repository.
- Confirm the gates team's Actions read access and `write:repository,read:organization` token read real job logs.
  Agents with Actions read have returned `404` for a log; the adapter's local documentation names the endpoints but
  gives no Forgejo token-scope recipe. The new reader check requests both successful jobs' logs and fails on a refusal.
- Confirm the approval API's statuses and containment of the merged probe commit. These Forgejo endpoints have not
  been exercised here.
- See each acceptance check fail with its role task removed, then pass with it restored. The planted-token matcher is
  included but has not been run against real verbose output, journal lines or task containers.
- Check the 25 external citation links left unchecked by the local document checker with networking disabled.

## Built

- The forge role adds and removes a marked host-name block, makes Porelo's forge identity and gates team, and pipes a
  missing token into the vault without putting the token in an Ansible variable, register, fact or file. It leaves
  `ansible_facts['getent_passwd']` untouched. Nonsecret status assertions report refusals outside `no_log`.
- The porelo role installs the Forgejo reader when the host's forge is enabled. Protection tasks manage `main` for
  every configured repository, compare settings before changing them and check the result afterward.
- Molecule checks cover the vault entry recreated by verbose up, the named TLS forge, gate pushes, approval and merge,
  the installed reader's Build2 socket contract with real job logs, token isolation and name removal at down. Both
  existing gathered-push merge paths use the person's approval and merge; their previous assertions remain.
- The local forge guide, both role guides and the changelog describe the account, vault entry, reader and protection.
- Local static checks parse the changed YAML, check the rendered Bash and compile its embedded Python. API stubs
  exercise unchanged settings, drift correction and missing-setting or HTTP refusals; CLI stubs exercise the token
  pipe's success and generation, vault-write and readback failures. The digest matcher was seen to fail on an embedded
  planted token before its correction and to pass plain, embedded and clean controls afterward.

- On the pinned Forgejo 17 image, measured: a branch protection takes and returns every setting written, the
  approvals' list as `approvals_whitelist_username` and the rule's hold over admins as `apply_to_admins`; a team made
  with `units_map` answers `permission` read, so the gates team is checked by its units alone.
- Molecule showed the plan's `/etc/hosts` line reach a task: Podman copies the host's file into each container, where
  `127.0.0.1` is the container's own loopback and hides the gate's address. The role `porelo` now makes the account's
  containers without it (`base_hosts_file = "none"`); a container keeps localhost and `host.containers.internal`.
- Molecule clears the person's forced password change by Forgejo's command line (`admin user must-change-password
  --unset`, measured): the role's admin token holds no `write:admin` scope, and the admin API answers it `403`.

## Plan corrections

- The original plan assumed a build-reader fallback to `git.token.<host>`. The available parser instead requires a
  nonempty `builds.credential`, and the build target reads exactly that entry. The guide names it explicitly.
- Both gathered-push paths needed to change: the direct B commit and the admin merge of `central/main`. The original
  plan named only the first.
- The build reader accepts `describe` and `serve <socket>` and speaks `org.fuin.porelo.Build2`; it has no one-shot
  verdict command. Molecule uses that socket contract, as the local adapter and build API code specify.
- Vault extraction uses `porelo vault credential --entry git.token.forge.porelo.internal get`, whose Git credential
  response goes to Git or a test consumer on a pipe. No general-purpose vault export command is assumed.
