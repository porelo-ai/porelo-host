# HO08 — The Forge With Its Registry

**Status:** Review.
**Size:** L - one role, but three accounts kept apart, a certificate the tasks trust, the repositories seeded from the
central forge without push mirrors, and a runner that may use KVM; it grew from M once read against
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
    forge, as an ordinary repository, not a pull mirror, since the tasks' gates push into it; no push mirror is
    configured. The person's central token reaches only the migration request. The gathered push runs elsewhere as
    a plain `git push` without force, which refuses when the central forge moved.
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
- **Divergent branches**: `verify.yml` requires no push mirrors, and `tasks/forge_push.yml` clones host main into a
  temporary directory as root and pushes it to central without force. It requires a non-fast-forward or fetch-first
  rejection and reads central A back; replacing the push with a forced one must fail the check because A is lost.

## Decided

- **QH21 (a), 2026-10-21:** Forgejo and its runner run under accounts of their own, `porelo-forge` and
  `porelo-runner`, never Porelo's.
- **QH22 (b), 2026-10-21:** the forge is a host setting, a variable porelo-frontend's `host up` writes into the first
  inventory, with no Porelo change.
- **The registry's credential for jobs (a), 2026-10-22:** an account `porelo-publisher` whose `write:package` token
  is an organization Actions secret, so every build publishes its snapshots, unreviewed task branches included; the
  token stays with the runner, outside every task. A run's own token cannot do it: Forgejo 17 answers `401` from
  `reqPackageAccess` when it writes the organization's registry, measured.
- **No push mirrors:** Forgejo's push mirror force-pushes and erases central commits, measured on the VM: central
  main held commit A and host main held commit B; sync answered `200` with no error and central A was gone. The
  operator's decision is to configure none. The gathered push is a plain `git push` without force, done elsewhere,
  which refuses when central moved.
- **GitHub's workflows run 1:1 on the forge (operator's decision):** only the values of variables and secrets differ,
  each present on both forges. So the runner offers GitHub's labels on an image close to GitHub's, takes actions from
  github.com by their pins, provides the JDK as `JAVA_HOME_25_X64`, and the organization holds the variables and
  placeholder secrets the workflows read; snapshots go to the forge's own Maven registry.

## Acceptance

- On the test VM `build/molecule.sh` makes: a repository migrated from a local stand-in for the central forge holds
  a workflow that runs on the runner and publishes into the registry; a second `up` changes nothing, migrates nothing
  again and registers no second runner.
- The migrated repository holds its content, is no mirror and has no push mirrors. After commit A on central main
  and B on host main, a root-owned temporary clone of the host repository pushed to central without force exits
  nonzero with a non-fast-forward or fetch-first rejection; central `contents/A?ref=main` still answers `200` with
  content `QQo=`. Git receives each token only through `http.extraHeader` in its environment, trusts the host's CA,
  and reads no global configuration; the check prints redacted push stderr and removes its clone in all cases.
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
    `porelo_host_forge_owner`, with no push mirror; the person's token for migration goes from
    `porelo-host/forge-central.token` on the drive into the request body on a pipe; a refusal names Forgejo's own
    answer per repository;
  - forgejo-runner `13.2.0`, pinned by digest, registered once with its token piped from `forgejo actions
    generate-runner-token` on standard input, a quadlet unit of `porelo-runner`; its jobs run in that account's podman,
    get no socket of it, and trust the host's CA through the same bundle, also exported as a passwordless PKCS12
    trust store mounted read-only for every job's JDK through `JAVA_TOOL_OPTIONS`; the runner offers the pinned
    Temurin 25 as `JAVA_HOME_25_X64`, as GitHub's image does;
  - the account `porelo-publisher`, in a team `publishers` of the owner's organization that may write its packages and
    nothing else, and its `write:package` token made by Forgejo's command line and piped into the organization's
    Actions secret `PORELO_PUBLISHER_TOKEN` through the API, once per forge; the token is never read out.
- **Molecule**, green on `8cab9fd`, 2026-10-21 21:55Z-22:04Z, with porelo `73ef80e0`'s packages: Forgejo answers through
  the VPN over TLS with the host's CA and listens on the VPN's address alone; a repository migrated from a stand-in
  central forge on the host itself (`forge_migrations_allow_local`) holds its content; the person's token appears
  nowhere in `ansible-playbook -vvv`'s output; a workflow committed to it runs on the host's runner and reaches the
  forge over TLS; a second `up` changes nothing. Each part
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
- **Molecule without the forge:** `PORELO_HOST_MOLECULE_FORGE=off`, with the pool off, checks that no forge account,
  home, trust directory, unit, quadlet, image in Porelo's account or listener remains; forge-on runs prove the same
  absence assertion goes red. Green on `fb4f706`, 2026-10-25 13:14Z-13:25Z.
- **Molecule from a running offline task:** its declared forge name resolves and HTTPS uses the task's own trust
  store; an undeclared registry name does not resolve, and curl without the host CA exits 60. The control was seen
  green where it must fail while OpenSSL's default store still held the host's CA, and now replaces it.
- **Molecule with divergent main branches:** a central commit A and local commit B precede a plain `git push`
  without force from a root-owned temporary clone of the host repository to central. Each side's token reaches git
  only through `http.extraHeader` in `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_0`/`GIT_CONFIG_VALUE_0`, with
  `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_SSL_CAINFO=/etc/porelo-host/forge/ca.pem`. The check requires a nonzero push
  exit and non-fast-forward or fetch-first rejection in stderr, prints that stderr with tokens redacted, and checks
  central main still holds A (`200`, `QQo=`); its temporary directory is removed in all cases. Measured: the push is
  refused with `! [rejected] main -> main (fetch first)`. The same check was red against the push mirror, which
  erased A.
- **GitHub workflows on the host's runner:** `ubuntu-24.04` and `ubuntu-26.04` use the same pinned act image beside
  `porelo-host`; changed configuration restarts the registered runner to declare its labels. Actions come from
  github.com by their workflow pins, and the organization's `PORELO_PUBLISH` variable is kept at `false` by default, `PORELO_DEPLOY_PROFILE` at
  `forge-release` and `MAVEN_SNAPSHOTS_URL` at the forge's Maven registry; a job publishes a POM there with the
  publisher's secret and a JVM reads it back (200) through the host's trust store.
  `JF_URL` defaults to `https://jfrog.invalid`, and `JF_ACCESS_TOKEN` is created with `porelo-host-placeholder` only
  when absent, keeping any existing value. Molecule reads the variables and secret names through the API and requires
  both jobs of each branch run to succeed, including checkout by its pinned GitHub action, the publishing variable's
  value, the repository's README and Node.js. The JVM probe runs on the mounted JDK (`25.0.5`), publishes a POM with
  the publisher's secret and reads it back (200); a store holding one public root is refused, which was seen to
  fail first while the control trusted the JDK's `cacerts`, made from the job's bundle with the host's CA.
- **Molecule with the forge, everything above:** green on `5b44fce`, 2026-10-25 15:57Z-16:13Z, 5/5 stages, the VM
  removed.

## Read against the skills

- `ansible-good-practices`, `ansible-new-role`, `ansible-new-collection`, `ansible-new-molecule`, each `2026.824.2`.
  `down` removes Forgejo's volumes, the API token, the runner's registration, the CA and the accounts' linger, so
  nothing of the forge starts again at the next boot. With no push mirrors, no stored mirror token needs cleanup.
  Also fixed: the subordinate ids read in each file, an unreadable one failing; the certificates made again before
  they end or when the address changes; the units retried until the VPN's address is there after a boot; the admin's
  token scoped to organizations and repositories only. Green on `b9bdccb`, 2026-10-21 22:24Z-22:34Z.
- **The plain push check:** a local fixture using real Git repositories and stand-in API and transport commands
  passes with a rejected plain push and A retained; a force-push mutation loses A and the same Molecule assertions
  fail. The fixture checks the per-side authentication environment, redaction of raw and Basic-auth token values,
  and temporary-directory removal after success and a clone failure.
