# HO08 — The Forge With Its Registry

**Status:** Implementing; the tasks' side blocked by porelo [B233](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b233) and
porelo [B234](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b234).
**Size:** L - one role, but three accounts kept apart, a certificate the tasks trust, the repositories seeded from the
central forge with their push mirrors, and a runner that may use KVM; it grew from M once read against
[PJ39](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj39)'s shape.

**What must be true.** Where the host's settings ask for one, a local Forgejo with its Actions runner and its
package registry runs on the host after `up`, holding the project's repositories as their upstream; the person
reaches it through the VPN, a task reaches its registry by name, and a project that asks for none comes up without it.
`down` stops it, and nothing is lost that the next `up` could not make again from the central forge.

## Plan

- **The playbook is the "outside"** where [PJ22](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj22)
  has the local Forgejo set up: outside `project.yml` and the project's tasks, before any task starts.
- **One role, `forge`, in `up`'s second play** after `porelo`'s `project.yml` part and before its tasks, since it needs
  the VPN, the vault open and the person's token for the central forge on the drive. Its task files:
  - `accounts.yml`: two system accounts of their own, `porelo-forge` for Forgejo and `porelo-runner` for the runner,
    each with linger and subordinate ids, never Porelo's account: a task's container must not share a user namespace
    with what holds the forge's admin and the person's token, and a job's code must not reach either. Only
    `porelo-runner` is let into `kvm`, through `base`'s `kvm.yml`, since porelo-host's own Molecule runs there.
  - `service.yml`: Forgejo in rootless podman as a quadlet user unit of `porelo-forge`, its image pinned by version
    and digest in `vars/main.yml`; its web, git-over-ssh and registry ports bound to the VPN's address
    ([HO05](README.md#ho05)) and to the address the tasks reach, never to the public one; its data in a volume the
    next `up` makes again.
  - `tls.yml`: a certificate for the forge's name from a CA made on the host for this run, its key readable only by
    `porelo-forge`; the CA's certificate handed to Porelo for the tasks' trust and to the person, never its key.
  - `admin.yml`: the admin account made once by `forgejo admin user create` inside the container, its password
    generated there and never read out; a token for the API made the same way and kept in `porelo-forge`'s home,
    readable by that account alone.
  - `repositories.yml`: each repository the project names created on Forgejo by migrating it once from the central
    forge, as an ordinary repository, not a pull mirror, since the tasks' gates push into it; a push mirror to the
    central forge configured on each with the person's token read from the drive by Forgejo's own command, never on
    a sync interval, since [BT06](https://github.com/porelo-ai/porelo-buildtools/blob/main/issues/README.md#bt06)
    starts each mirror through the API.
  - `runner.yml`: `forgejo-runner` as a quadlet user unit of `porelo-runner`, its image pinned the same way,
    registered once with a token made by `forgejo actions generate-runner-token` and handed over on standard input;
    a second `up` finds `.runner` and registers nothing again. Its labels are the runner names the workflows use,
    and its jobs run in containers of `porelo-runner`'s podman.
  - `publisher.yml`: an account `porelo-publisher` in the project's organization, its `write:package` token made
    inside Forgejo's container and set as the organization's Actions secret through the API on a pipe, so every
    build, an unreviewed task branch's too, publishes its snapshots into the registry; the token is never read out,
    stays in Forgejo and the runner's jobs, and reaches no task.
  - `down.yml`: the runner's and Forgejo's units stopped, after the store's last copy and before the vault; nothing
    kept, since the next `up` migrates the repositories again and the builds fill the registry.
- **Whether it runs**: a host setting, not a project's - the boolean `porelo_host_forge` (default `false`), which
  porelo-frontend's `host up` writes into the first play's inventory beside `porelo_host_account`; the role runs only
  where it is `true`, and Porelo changes nothing for it.
- **Credentials made on the host, kept on the host**: the admin's password, the API token and the runner's token are
  made inside Forgejo's container; the person's token for the central forge goes from its file on the drive into
  Forgejo by the shell's redirection, as `porelo vault put --from-file` takes a key. None of them is a variable, a
  fact, a register or a task's output, and every task touching one carries `no_log`.
- **Red first**: `verify.yml` pushes a generic package to the registry and reads it back through the forge's name
  over TLS, and asserts that the public address refuses the forge's ports; it fails with the forge bound to all
  addresses. A second test plants a value in the token file on the drive and greps `ansible-playbook -vvv`'s output
  and the journal for it, as [HO02](README.md#ho02) does.

## Decided

- **QH21 (a), 2026-10-21:** Forgejo and its runner run under accounts of their own, `porelo-forge` and
  `porelo-runner`, never Porelo's.
- **QH22 (b), 2026-10-21:** the forge is a host setting, a variable porelo-frontend's `host up` writes into the first
  inventory, with no Porelo change.
- **The registry's credential for jobs (a), 2026-10-22:** an account `porelo-publisher` whose `write:package` token
  is an organization Actions secret, so every build publishes its snapshots, unreviewed task branches included; the
  token stays with the runner, outside every task. A run's own token cannot do it: Forgejo 17 answers `401` from
  `reqPackageAccess` when it writes the organization's registry, measured.

## Acceptance

- On the test VM `build/molecule.sh` makes: a repository migrated from a local stand-in for the central forge holds
  a workflow that runs on the runner and publishes into the registry; a second `up` changes nothing, migrates nothing
  again and registers no second runner.
- The forge's ports answer on the VPN's address and refuse on the public one; the registry is reached by the forge's
  name over TLS with the host's CA.
- A planted token's value appears nowhere in `ansible-playbook -vvv`'s output, the journal, or the facts cache.
- A job of a branch nobody reviewed publishes a snapshot with `porelo-publisher`'s secret; the same token is absent
  from `-vvv`'s output, the journal and a task's container, and a job without the secret is refused (`401`).
- A host without `porelo_host_forge` is left without Forgejo, its image, its accounts, its units or its ports.
- After `down`, no unit of `porelo-forge` or `porelo-runner` runs.

## Built

- The role `forge`, run in `up`'s second play after the porelo role's project part where `porelo_host_forge` is true,
  and stopped first at `down`:
  - the accounts `porelo-forge` and `porelo-runner`, with linger and subordinate ids, from the user module's own answer
    (`getent` would replace the facts the porelo role reads after it); only `porelo-runner` in `kvm`;
  - a CA made on the host (`/etc/porelo-host/forge/`, its key root's alone) and the forge's certificate for the VPN's
    address and `forge_name`; one bundle of the system's CAs and the host's, which Forgejo's Go and its git both read
    whole (`SSL_CERT_FILE`, `GIT_SSL_CAINFO`), since git does not read a directory without OpenSSL's hashed names;
  - Forgejo `17.0.0-rootless`, pinned by digest, a quadlet unit of `porelo-forge`, HTTPS and ssh published on the
    VPN's address alone;
  - the admin made by Forgejo's command line without a forced password change (a user that must change its password
    has its token refused), its token written by the shell into a file only that account and root read;
  - each repository of `porelo_host_forge_repositories` checked as agreed with porelo-frontend, migrated once into
    `porelo_host_forge_owner`, with a push mirror back on no interval; the person's token goes from
    `porelo-host/forge-central.token` on the drive into the request body on a pipe; a refusal names Forgejo's own
    answer per repository;
  - forgejo-runner `13.2.0`, pinned by digest, registered once with its token piped from `forgejo actions
    generate-runner-token` on standard input, a quadlet unit of `porelo-runner`; its jobs run in that account's podman,
    get no socket of it, and trust the host's CA through the same bundle;
  - the account `porelo-publisher`, in a team `publishers` of the owner's organization that may write its packages and
    nothing else, and its `write:package` token made by Forgejo's command line and piped into the organization's
    Actions secret `PORELO_PUBLISHER_TOKEN` through the API, once per forge; the token is never read out.
- **Molecule**, green on `8cab9fd`, 2026-10-21 21:55Z-22:04Z, with porelo `73ef80e0`'s packages: Forgejo answers through
  the VPN over TLS with the host's CA and listens on the VPN's address alone; a repository migrated from a stand-in
  central forge on the host itself (`forge_migrations_allow_local`) holds its content, is no mirror and has its push
  mirror back on no interval; the person's token appears nowhere in `ansible-playbook -vvv`'s output; a workflow
  committed to it runs on the host's runner and reaches the forge over TLS; a second `up` changes nothing. Each part
  seen red first without it: the CA and Forgejo, the migration (404), the runner (no run taken).
- **Molecule with the publisher**, green 2026-10-22 05:25Z-05:35Z, 5/5 stages, the VM removed, porelo run 928's
  packages:
  - a workflow on a branch nobody reviewed runs twice on the host's runner, the second time with the token made anew
    by an `up` under `-vvv`;
  - each run is refused by the registry with its own token (`401`) and publishes with the secret a package that
    holds the digest of the secret;
  - no 40-digit hex string in that `-vvv` output, in the journal or in the environment of the account's task
    containers has that digest.
  - Seen red first without `publisher.yml`: both runs failed at the publish (`curl` exit 22). The search was seen red
    on a made-up token, planted in each of the three places, and green without it; the real token is never printed.
- **The Build's jobs on `ubuntu-26.04`**, the Molecule job's runner packages pinned to 26.04's versions, as this host
  runs them; first read in the Build after the push.

## Read against the skills

- `ansible-good-practices`, `ansible-new-role`, `ansible-new-collection`, `ansible-new-molecule`, each `2026.824.2`.
  Fixed, the first with a test seen red: `down` left the person's token in each push mirror's git configuration
  inside Forgejo's volume, with the API token, the runner's registration and the CA, and the accounts' linger would
  have started the forge again at the next boot; now `down` takes all of it off the host. Also fixed: the subordinate
  ids read in each file, an unreadable one failing; the certificates made again before they end or when the address
  changes; the units retried until the VPN's address is there after a boot; the admin's token scoped to
  organizations and repositories only. Green on `b9bdccb`, 2026-10-21 22:24Z-22:34Z.

## Waits for

- **The tasks' side:** a task reaching the registry by a declared name, and the host's CA in a task's trust store,
  are porelo [B233](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b233) and porelo [B234](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b234).

## To be checked

- Whether a migration keeps a repository current when the central forge moved while the host was down: a fresh
  `up` migrates anew, but a repository the central forge changed during a sprint (an action move merged there)
  makes the gathered push fail; measured with a stand-in, and written into
  [BT06](https://github.com/porelo-ai/porelo-buildtools/blob/main/issues/README.md#bt06) if it holds.
- Whether Forgejo's runner runs the workflows' `runs-on` labels in a container image close enough to GitHub's runner,
  or each repository's workflow needs a variable; that is
  [PJ22](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj22)'s third part, measured here on one repository.
- A host without `porelo_host_forge` left without anything of the forge: the scenario runs with it on, so a second
  scenario without it is still to be made.
