# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- `down` no longer counts a host admin's own membership: an organization always has a host admin, so a host that
  followed one could never be taken down. Any project membership still stops it.
- Follow, forge gate and pool units use the pinned native host package. The collection installs the forge hook at
  the native follow's link target; each push to the host's forge is judged by `porelo-host judge-push`.

- Molecule and the move rehearsal require a selected local host package beside Porelo's packages, install them before
  the first up and pin their Debian versions. Verification rejects a different host build and retained legacy programs;
  organization follow, gate measurement and pool acceptance use native commands.

- Pin the `porelo` and `porelo-host` packages from the same signed source, compare the installed host version,
  and restrict person sudo access to six packaged token, task and follow rules with a reset environment.
  Remove host program sources.
- Move the development VM tool to `build/`, outside the installed collection, and retain only the pre-receive hook,
  pre-installation check, measuring program and pool VM give-back as collection script exceptions.

### Added

- **A person has the host follow its organization at once.** The person sudo rules add a sixth,
  `porelo-host org follow-now` with no argument at all (`""`), so an admitted person, as `porelo host follow` does, starts one
  follow pass and waits for it instead of for the five-minute timer; anyone else is refused by sudo.
- **The half of the host for jobs and the VM pool is a setting.** `porelo_host_work_share`, the percent of the
  host's processors and memory the forge's jobs and the VM pool may take together, from 1 to 100; unset 50, as
  before. The check refuses a value outside that before anything is installed, the forge's capacity and the pool's
  memory refusals name it, and above 50 `up` writes a note that the host's own work keeps less than half.

- **A host's builds also read the upstream snapshots.** Each new organization on the host holds
  `MAVEN_UPSTREAM_SNAPSHOTS_URL`, Sonatype's snapshots, which a repository's `forge` profile reads without a token for
  the `org.fuin.porelo` snapshots the host's registry does not hold, such as a parent pom.
- **Porelo's commands on the host's forge take a lend of their own.** `porelo-host-person forge-token --lend` makes a
  token of the person's login for one command, beside the person's token, and deletes only lends a day old;
  `forge-token` replaces every token but the lends younger than a day. A gate command or a task start that asks for a
  lend no longer deletes the `<forge>.person` token a task's builds watch reads from the vault.
- **A task on the host reads its Builds from the host's forge.** Each project's file on the host names `builds` beside
  `fetch_from`: the forge's API on the git port and the person's `<forge>.person` vault entry, so a guarded project's
  task reads the Builds of its pushes while its `project.yml` stays the same everywhere.
- **A host carries single repositories of a project.** Where the organization's state names the host's
  `repositories` of a project, the follow takes only those and the project's own; one named no longer is taken off the
  host's forge by `porelo-host-project take-off`, held while its work is not at the central forge, its deploy key
  deleted with a token or named for its owner. `org status` says `not-carried` and `held` per repository.
- **A task's token also reads packages** (`read:package`), so a task can resolve its project's snapshots from the
  host's forge. It reads those of every organization its person's task account is in and writes none; Porelo's task
  gate holds a task to its own project's.

### Fixed

- **A task's account pushes only its own person's task branches.** The host's push judge refuses an update or deletion
  from `porelo-<login>` to any ref but `porelo/<task>` of that person's recorded tasks, so one task's token no longer
  writes another person's task branch, a tag or a new branch. Force-pushing its own `porelo/<task>`, as an amend does,
  stays allowed. The forge's hook now tells the judge the pusher.
- **A burst of connections no longer stops a gate socket for good.** The forge's web, git and runner gates, the push
  judge and the Matrix client gate set no trigger limit, which systemd met by failing the socket and deleting its path,
  so every request through the window's forward came back empty. Each bounds its connections at once, and up fails
  when one of them is not listening.
- **A host's first up waits out an outage of GitHub's release downloads.** The forge role fetches the runner's pinned
  JDK again on a 5xx or no answer, a body broken off included, every 2 minutes for 14 minutes with a 60 s timeout,
  instead of once with 10 s; a 4xx, a refused certificate, a wrong digest or a full disk still fails at once.
- **The move check finds the push in the forge repository that holds the task's branch** instead of asking for the
  repository's key, under which the host's forge holds none; a Build line whose reader sees no `builds:` fails; and
  each failing line says what the forge (`HTTP <code> for <path>`), Git or the vault answered.
- **Work ahead of central is said and holds the give-back.** In `org status` a `taken` repository carries `central`,
  how its `main` on the host's forge stands against central (`ahead` with its commits, `up-to-date`, `moved-on` or
  `cannot-say`); `taken` alone only ever said it was migrated. `down` refuses, before anyone is purged, while a
  repository's work is not known to be at central, unless the host is given back anyway.
- **The forge's web gate names its two working addresses when it refuses a foreign Host.** The addresses come
  from the forge's settings; other refusals and unreadable settings keep an empty response.
- **A person puts their forge token in the vault before the first push.** `porelo-host-forge-token` puts the admitted
  person's token for the host's forge into Porelo-Vault as `<forge>.person` before their tools read the forge over git.
  Push and pull refresh it through the same helper; a refused vault write warns while the transfer continues.
- **The host reads the project file's `central` alone.** A row's `upstream`, a host's address the project file no
  longer holds, no longer decides whether the project's own repository stays open to merges, and the host keeps none.
- **A project's `why` in `org status` says each like reason of its repositories once,** as `<names>: <reason>`, and
  a repository the project file gives no central address no longer stands in it; `repositories[]` keeps each row.
- **The move check reads each line where its fact is held.** The pushed commit comes from the task's branch on the
  host's forge or the next free one the gate's approve took, with the person's vault answering Git. The pull request
  comes from the forge's open requests for that branch targeting the repository's default branch, using the same
  credential. Both checks work without build monitoring. The Build line passes with `not configured` without a
  `builds:` block; other build-reader errors fail. The conversation line counts a message the task sent into the
  project's conversation, since `porelo talk peers` never lists a project's own tasks.

### Security

- **The forge's web gate serves the forge's own site alone,** so another page in the person's browser cannot act as
  them: a `Host` other than the forge's name or `127.0.0.1` on its port gets `403`, and so does a request that changes
  something from another origin or site. On the laptop, Maven reaches the forge's packages by `127.0.0.1`.

## [0.5.12] - 2026-11-05

### Fixed

- **A person admitted before their project was carried reaches the Matrix gate.** Their `porelod` was started
  without `porelo-people`, which they joined later, so the first task start failed at the gate's socket. The
  follow now restarts such a user manager where no container of the person runs, and admission joins the group
  before linger starts it.
- **A project file signed anew reaches the host's copy.** The follow brought the project's own `main` only up to the
  file's last change, below an empty commit that signs it anew, so Porelo refused every task there for an unsigned
  file. It now goes to the newer of the two, as Porelo judges the file.
- **A pool VM's clock is set from the host's after each revert,** by a guest agent each VM now has, as a revert brings
  back the snapshot's clock and `apt` then refuses what was published since. The VM's link stays down until it is set.
  A VM whose clock cannot be set stays off and says so; `up` refuses a pool made before this, naming `down` and `up`.

## [0.5.11] - 2026-11-05

### Added

- A measuring playbook for disposable machines, with private JSON results and a machine page built from result files.

- **Role `check`, one read-only look at a machine before anything is installed,** naming every lack at once with what it found, what
  was asked and what to do, as JSON for the interface; `up`'s first task runs the same code. `forge`'s job budget is its formula now.

### Changed

- **`doc/ssh.md` says what a login closed at once is,** sshd's own penalty by its default, and what to do: wait.
- **`org status` names each repository of a project's signed file,** taken, waiting and why, or with no central address, which stands in the
  project's `why` too.

- **KVM and libvirt only where `porelo_host_kvm` says yes, off by default,** and the CPU asked for `vmx` or `svm` only there, so a
  server without virtualization can be a host. A VM pool without it stops before anything is installed. A host running jobs that
  make a VM must now say yes. The runner joins `kvm` only there.

### Removed

- `base`'s `tasks_from: account`, which nothing called.

### Fixed

- **A login of 32 characters is taken everywhere it is read,** by `porelo-host-person` and the `matrix` role, which
  stopped at 31.

- **`up` waits up to 5 minutes for a package run to end,** at its check and at each `apt`, rather than stopping at
  Ubuntu's own daily one.

- **`down` says the firewall stays on,** with the command that takes it off, in a new `note` line of the callback.

- **`up` refusing root's key file says why:** which file, how many keys of which kind it holds, and what to do, printing no key.

## [0.5.10] - 2026-11-04

### Added

- Each follow names each person's projects to that person alone, in `organization/persons/<login>.json`, so their account
  can list them before a first start there. Needs a Porelo that reads it.
- `build/move-check.sh`, the read-only check of an agent's move, and `build/room-tunnel.sh`, which lets a person's tasks on a
  host reach the room on the development machine over one socket.
- Each project's organization on the forge holds `PORELO_PACKAGES_READ_TOKEN`, which can only read its packages, and, where
  the host has a VM pool, `PORELO_POOL_SSH`. A project registered before keeps what it had.
- The follow reads each project's signed file: the host takes every repository it names under `central` with one token,
  and each repository's `main` needs a review or not as `review` says (`required` by default). Needs a Porelo with
  `project verify`.
- A server's pin also holds the Organization Admins' keys, when Porelo names them, so a Machine Admin they replace
  takes effect at the next follow. Root stays with the machine's listed admins, and the role gets no account.
- `porelo-host-push --central <project>` tells a project's member, with no token and no root, how each repository's
  approved `main` stands against the central forge, as the follow last read it with the host's read key.

### Changed

- A refused project helper gives its own last line and exit code as the project's `why` in `org status` and in the
  follow's journal, never its other output or the central token. A refused migration's `why` stands until a later try
  ends, instead of ending with the next follow.
- A project's deploy key at the central forge is titled `porelo host <host> project <project>`. `porelo-host-project
  remove` answers each key it leaves there in `left_at_central`, and the follow writes it to its journal.

### Fixed

- The VM pool's run key reaches the forge behind its gate again, on its socket, without the old address or `ca.pem`, for sending and for deleting at `down`, and every project's organization holds it, not one no follow makes.
- The follow holds a repository to the signed review and merge values whatever the case of its rule on `main`, and leaves no second rule there.
- `MAVEN_SNAPSHOTS_URL` names `localhost`, as Maven's default mirror refused the plain http of `<host>.localhost`.
- What a Project Admin files at the central forge reaches a task on the host at the next follow, once Porelo accepted it.
  A task reads the project's file from the host's forge, whose copy was taken once.
- A project that lists repositories takes no merge in its own repository on the host, whose `main` follows the central
  forge. One that lists none keeps its merges there.
- A project put on a host, taken off and put on again is taken: its migration replaces the read-only key this host made
  for it, where the central forge refused a second key of that title. Another host's key stays.

## [0.5.9] - 2026-11-03

### Added

- Root's `org follow` and `org refresh` take the signed organization through Porelo's fetch command, reconcile
  persons and project memberships, publish member-readable project files and Porelo's signers, and purge accounts
  seven days after their last membership is lost. Status includes the organization's state, carried projects and the
  account deletion day. `org refresh` takes the host admin's central token once to add the host's read key.
  A persistent five-minute follow timer uses the organization's deploy key, settings, pinned forge keys and host
  admin keys installed at setup; the host summary includes the deploy key's public half. `org pin` is removed.

### Changed

- `porelo-host-person org status`, root's alone, answers the host, the applied organization commit, the pinned
  fingerprint and each person's state (`active`, `locked`, `pending`, `purged` or `named`), whether they are host admin
  and their project memberships; `org` answers `host` and `persons` the same way.
- The host follows the organization alone. It puts a project on when the state names it: members admitted, its forge
  organization with teams, variables and publisher, its repository migrated with the central token `org refresh` takes
  once, `main` protected, its room kept with `keep-room`. It takes one off when the state no longer does, unless a
  commit on its forge is unpushed, then the project stays `held` and named. The public read-only deploy key stays at
  the central forge for a person to remove by hand. A forge organization now belongs to the forge's administrator as
  well, as Forgejo keeps a last owner.
- A project's file on the host names the host, so a member's Porelo can say where the project stands.
- Root's login follows the state's host admins at each follow, and a later `up` leaves it so. Before the first follow
  `up` adds the seed to root's keys and removes none.
- A purge also deletes the person's and their task gates' forge users, and needs no transport on a host with no
  homeserver.
- With `forge_runner_capacity`, `forge_job_cpus` or `forge_job_memory` unset, the forge takes the largest that fits
  half the machine beside the VM pool, 2 jobs of 4 CPUs and 8g on a large one, with a floor of 1 job, 1 CPU and `768m`;
  it refuses only if that floor does not fit, or a value set does not. `forge_job_omp_num_threads` follows the CPUs.
- `down` also removes the follow, its units, the organization's keys and the setup's files, and takes the record of a
  person locked with a day.
- Each push to the host's forge is judged when it arrives: a pre-receive hook asks root's `porelo-host-person
  verify-push`, which has Porelo's `commit verify` judge every new commit against the project's keys in force, their
  certifiers of the project's own tasks, the KRL and the project's task certificates valid now, refuses the push
  otherwise (taking the quarantine as git names it, `.` segments included, never a `..`, in a volume of the forge's or
  its container root's), and appends each accepted
  commit's verdict to `/var/lib/porelo-host/arrivals/<project>/<repository>.jsonl`. Sync arms each new repository after
  the migration and records its history as `migrated`, stopping when the hook link would not hold;
  `arrivals <project> <repository>` reads the record, and removing a project takes it along.
- Push, pull and migrate put the person's new forge token into their vault as `<forge>.person`, so it stays the one in
  force; a task certificate with any principal beside `task:<project>:<task>` is refused by the host itself; a missing
  or unsafe KRL at a task start is 69.
- Each person's runtime directory `/run/porelo-host/people/<login>/` holds the link `porelod.sock` to their daemon's
  socket, restored at boot, so the tunnel's daemon and return sockets (`return.sock`) follow from the login alone.
- Git reaches the host's forge on `127.0.0.1:<git_port>` through the same token-only gate as `git.sock`, so the gathered
  push and pull run in the person's own account without sudo, and no private network namespace or forwarder is made per
  transfer. Forgejo never listens on TCP; the browser's and the runner's gates refuse a TCP connection. `up` removes
  the push's sudoers rule, and `porelo-host-person forge-token --for` is gone.

### Fixed

- `down` stops a running follow before it checks memberships, so a follow's first state cannot admit anyone while the
  host is taken down, and starts its timer again when the check refuses.
- A repository named with capitals reaches members' push configuration and its removal, on the forge's lower-case path.
- An interrupted read key generation or manifest write no longer leaves a project that cannot be taken off.
- An organization admission retried finishes subordinate IDs and linger before access is restored.
- Project migration accepts a quoted `repository:` setting, keeps an explicit SSH port for the comparison at removal, and
  refuses the repository name `repositories.json`.
- `porelo-host-person add`, and sync for each person it admits or unlocks, starts the person's `porelod` with `porelo
  setup` (`systemctl`, `runuser` and `env` checked on the fixed path first), so their tunnel reaches a daemon before
  their first bring; an admitted account gets `umask=0022` in its GECOS field, so
  Ubuntu's usergroups `002` no longer makes directories Porelo refuses as group writable.
- Sync arms a repository through Forgejo 17's shared hooks directory (its git's `core.hooksPath`), whose `pre-receive`
  runs each repository's `hooks/pre-receive.d`; it no longer waits for a `hooks/pre-receive` Forgejo 17 never writes
  into a repository, which stopped every sync after a migration with "runuser failed (exit 4)".
- `porelo-host-push --migrate` gives Forgejo the central token as the password of `x-access-token`, which a git
  migration clones with and GitHub takes for an App installation token as for a person's; `auth_token` it ignored.
- `porelo-host-person sync` no longer calls the Matrix transport's `members`, which is the project admin's verb and
  refused the host's call with 64, failing every sync; the gate admits each login by itself. Its arming of pushes no
  longer stops with 6 on a forge that never held a repository.
- Lock and purge, and every lock a sync or a project's removal makes, end the person on the homeserver again: the
  Matrix transport's `expel` gets the homeserver administrator's token from the gate on its stdin, never on a command
  line, where before it refused with 78 and the lock stayed pending.
- Every command the host's helpers run as a person or a service account starts in `/` with that account's own `HOME`,
  so a lock run by root over SSH no longer fails where the account cannot enter root's working directory.
- Person revocation tolerates missing Linux accounts, rejects shared purged keys, preserves lagging project cards,
  and validates lock retry dependencies. Local removal survives service failures, and lagging cards honor access
  losses. Unfinished locks retry across runs, and cleanup failures retain their retry state.
  Pending locks preserve new revocations and shared records, while deferred access honors every expiry bound.
  Cleanup preflights dependencies and deletes temporary admin tokens; host lock reasons and pending access
  restrictions survive retries and project removal.
- The runner comes back when its proxy restarts, a stopped proxy removes the jobs left in its namespace, and jobs get a
  read-only name table of root's and the host name localhost, so a job's own container cannot take the forge's name for
  later jobs (`docker://` steps and the shared resolver file still can). The runner gate's Bearer
  support and its refusal of artifact v4 transfers are documented.
- Gathered push validates raw caller config bytes and opened descriptors, keeps Git helpers in its cleanup group,
  and handles early coprocess exits and NUL output safely.
- Gathered push refuses sudo callers of the root-only check, bounds caller configuration reads and isolates token
  helpers from credential stdin. Namespace forwarding preserves early gate responses on socket errors, times out
  idle sockets and stops Git descendants and removes temporary clones when the helper receives a signal.
- Project sync requires each person's key and expiry to match the host's applied organization. SSH revocations remain
  cumulative, project removal clears membership and signer publications, and person locks preserve verified Matrix
  admins while attempting each service revocation independently. Forgejo team sessions include organization scopes,
  unlock skips absent identities, and lock and purge recover when a locked person's Linux account is gone.

### Changed

- Project sync takes Porelo's verified role `admin` or `developer` and records an admin as the project-admin
  membership; any other role in the verified access is refused.
- A task certificate names exactly one principal `task:<project>:<task>`, or `task:default:<task>` for a task
  without a project, of a project the person is a member of. Before it is recorded, Porelo's `task
  check-certificate` judges it against the person's key in force and the KRL in a unit with no home and no network.
- Bring and join take the person's forge token from `sudo -n porelo-host-person forge-token` at each run into their
  vault entry `<forge>.person`; the play keeps it in the person's runtime directory until its end.
- Root alone brings an organization bundle on stdin with `org --stdin`, so a fresh host can take its first
  organization before any account holds a setup directory.
- Gathered push and pull run through sudo for the current project developer. Local API traffic uses the forge gate's
  Unix socket; each local Git transfer uses a private root network namespace and a credential pipe, with no host TCP
  listener, local CA or vault token. Migration stays in the person's account and obtains its local token on demand.

- Host persons come from verified cards with one SSH key and optional expiry. Project roles and locks reconcile
  forge teams, Matrix rooms and project-local allowed signers; other projects and sessions stay. Host locks,
  current-key revocation and last-membership removal end sessions and revoke forge tokens. Purged logins cannot
  return. Replaced signer keys remain bounded to their historical validity.
- SSH on port 22 is the public entry point. Root-owned key files, an atomically published KRL, private person
  return-socket directories and forwarding restrictions replace VPN access. Lock ends sessions and the user manager;
  the organization reader can supply card keys, expiries and host-wide revocations through the person helper.

### Removed

- `porelo-host-person add` and `lock`, `porelo-host-project`'s handling of person locks, the host's bring and join, the
  access file, the Matrix admins file, the forge's role tasks for one project's organization and the options
  `forge_repositories`, `forge_owner` and `forge_agents`, the task entry point of the Porelo role with its host and trust tasks, the migration stop in
  `porelo-host-stop` and `porelo-host-push`, and every reading of the old record, registration and signer shapes.
- Device records, per-device credentials and addresses, and credential stdin for person admission. Project sync no
  longer reads access-file host CA values or grants commit-signing authority to the project's verification key.
- The VPN role and the WireGuard stop. Up and down remove a legacy WireGuard interface and its files.
- The `identities` stop and the forge role's lasting gate token (`gate.yml`, `forge_porelo_account`): a person's
  token is made at each bring and join, a task's at its start.

### Added

- Matrix clients use the transport's system socket gate as `porelo-matrix`, restricted to `porelo-people`.
  The homeserver uses a private Unix socket, with gate preparation before startup and no role-managed TLS or TCP
  publication. Project sync atomically publishes verified room admins, project removal deletes them, and purge
  expels the login through the transport. Admission no longer issues Matrix machine or registration tokens.
- Separate Unix socket gates for browser and token-authenticated Git/API access to Forgejo. Browser identity comes
  from the admitted host account; caller identity headers are removed and browser credential-setting routes refused.
  Forgejo uses a private Unix socket with no TLS or SSH listener; certificate requests and the password helper go.
- Host task certificate recording, lookup by task key fingerprint, per-task forge token creation and deletion, and a
  daily expiration sweep. Certificate validation uses OpenSSH and the person's current key in the applied organization;
  records are private and append-only.
- On-demand person forge tokens answered directly on stdout, token-free admission, and all-token deletion on
  organization revocation with retry after an API failure.
- `porelo-host-person org`, run by root or `sudo -n` by the host admin pinned once at setup with `org pin <login>
  <key>`, takes the host's projects and persons from the organization bundle the host admin uploads into
  `porelo-host/setup/registry.bundle` in the data folder: Porelo's `registry verify` checks it in the sync's isolated unit
  against the pinned key and the last applied commit, refusing a foreign signer or an older or forked state whole. Bad
  entries are named alone while the rest applies, a revoked login stays revoked, a verified handover moves the pin,
  and the answer is recorded root-only in `/etc/porelo-host/organization/applied.json`. A project the organization no
  longer names for its admin is named in the answer and kept.

- `porelo-host-person sync <project>`, callable by root or `sudo -n` by the project's unlocked recorded admin through
  the `porelo-people` sudoers rule, copies the admin's plain private `project.bundle` and `access.bundle` into a
  root-only `/run/porelo-host/sync/` directory and verifies them through `porelo project verify --json` in a
  `DynamicUser` transient unit without home or network against the project's pinned signing keys and last applied
  commits. Verified persons determine project memberships, SSH card keys, forge teams, Matrix rooms and allowed
  signers; removal locks an account when its last membership ends. Sync records `commit=`, `access_commit=` and
  bundle-verification `signer=` lines in `/etc/porelo-host/projects/<project>.conf`.
- `porelo-host-project` registers a project for a recorded person, with its pinned SSH Ed25519 signing key, forge
  organization and package-only publisher. Removal checks every repository's commits against the central forge
  before deleting its repositories, packages, organization, publisher and root-only record.
- A root person helper admits project admins with root-owned SSH key files and private records, and locks or purges
  their host accounts. Admission creates their forge login and gate, and makes no forge token. Lock disables the forge
  identities and deletes their tokens, expels Matrix accounts and revokes registration in one operation, and removes
  delivered credentials and their runtime directory. A separate install task provides the helper, SSH key lookup and a
  no-argument forge-password sudo rule.
- `porelo.host.bring` and `porelo.host.join` run in the person's own account with no `sudo` but forge-token's and
  sync's: the setup's files in `porelo-host/setup/<project>/` in the data folder checked, Porelo's verify on the project and
  access bundles and the project followed; the bring migrates the project's repositories with the admin's own forge
  token, protects `main`, makes the teams `developers`, `gates` and `agents`, sets the Actions variables, runs `sync`
  with a user timer and makes the room once Porelo can; both write the person's push config. `porelo-host-stop --stdin`,
  run without `sudo`, gives the caller's own `vault-new`, `vault`, `keys` and `forge-central-token`.
- `up` installs every agent package the repository publishes, read from the packages providing `porelo-agent`, and
  Porelo's message filter with rootless networking; a repository publishing no agent stops `up`.

### Changed

- `porelo-host-person sync <project>` and `porelo-host-project add <project> <admin>` refuse a project the applied
  organization does not name for that admin.

- The forge runner, registration and jobs share a loopback proxy to a dedicated token-only gate socket. Checkout,
  package access and the Actions cache no longer depend on the VPN address or published runner ports; jobs no longer
  receive forge CA trust mounts. Existing runner registrations keep their token and use the loopback web port.

- `porelo-host-push <project> [<repository>...]` runs in any project developer's own account (refusing root and `sudo`
  with `77`), reading `porelo-host/push/<project>.conf` in the config folder (`0600` plain file in a `0700` directory of the
  caller's `getent passwd` home, never `$HOME`) and the caller's `<forge_name>.person` token from their vault (refusing
  a missing entry with `69`, naming it and `porelo-host-stop --stdin identities`) while prompting hidden on the terminal
  for their central forge token; without repository names it pushes every repository in the config's order. `up`
  installs `/usr/local/sbin/porelo-host-push` (`0755`) and `/etc/porelo-host/forge/central-ca.conf` (`0644`), and
  `porelo-host-project remove`'s `--check` reads each repository's central address from Forgejo's `original_url`
  instead of `/etc/porelo-host/forge/push.conf`, refusing any repository without one by name.
- Person records in `/etc/porelo-host/people/` store ordered `member=hand` and `member=<project>
  project-admin|developer` memberships in place of `role=` and `projects=`; an existing `role=project-admin` record with
  no `member=` line is read as `member=hand` and rewritten on its next write. `porelo-host-person add` records
  `member=hand`, `lock` keeps memberships, `porelo-host-project add` records `member=<project> project-admin` for any
  unlocked member, and `porelo-host-project remove` drops the project's memberships, locks anyone left with none, and
  reports `"locked"` in its JSON answer. `porelo.host.down` checks `/etc/porelo-host/people/` first and refuses before
  stopping anything while any record holds a membership, naming each person and their memberships with `"Take the
  project off"` and `"Purge"`.

### Removed

- `/etc/porelo-host/forge/push.conf`: `up` no longer writes root's shared push configuration, and nothing reads it.
- Admission makes no `<agent>-<user>` forge identity, and `up` no longer writes `agents=` into
  `/etc/porelo-host/forge.conf`: Porelo lends agents no forge identity of their own. Lock still revokes those a 6j
  host made.
- The default `operator` forge login, `forge_person`, `person=` in `/etc/porelo-host/forge.conf`, and direct-root calls
  to `porelo-host-forge-password` (now refused with `64` unless run through `sudo` as an admitted person). On an
  existing host, `up` deletes a forge user `operator` that has no record in `/etc/porelo-host/people/` and rewrites
  `forge.conf` without `person=`, so a person named `operator` can be admitted like anyone else.

### Fixed

- A failed admission after the account exists leaves the person locked and recorded, so purge can remove them; a
  failed purge leaves the account expired. A locked person can neither be admitted again without purge nor own a new
  project. A forge failing in itself is reported as something missing (69). SSH reads the people's keys as soon as
  `up` has written its drop-in.
- A sudo call to the forge-password helper changes only the caller's own login and requires their unlocked,
  root-owned person record.
- SSH for the `porelo-people` group reads only root's VPN-restricted authorized keys, so a person cannot add an
  unrestricted key in their home. Other accounts retain their existing key lookup.
- `down` gives the host back when only a room's transport could not clear what it keeps with the vault, such as a
  homeserver taken off the VPN before the give-back. An open vault is then cleared with `--force` in a step of its own
  name; anything else Porelo does not remove still stops `down`. It needs Porelo's `vault clear --json`.

## [0.5.8] - 2026-10-28

### Fixed

- The host comes back from a reboot: the firewall's unit leaves systemd's default ordering, which on an image running
  cloud-init's network stage before `sysinit.target`, such as Scaleway's Ubuntu, closed a cycle that held the boot.
- `up` follows the project again when the interface uploads a newer bundle at the same path: before, a commit the
  person signed after the first `up` stayed unfollowed, since only a changed address or key led to a new follow.
- The forge's runner takes 2 jobs at once by default, not 4, so `up` with the defaults passes the capacity check on the
  16 processors of the server Porelo rents instead of refusing it.

## [0.5.7] - 2026-10-28

### Added

- The host joins the project's room on the person's own computer during the move: the VPN role writes the marked
  line `<the person's VPN address> matrix.porelo.internal` into `/etc/hosts`, the stop takes `--stdin matrix-token`
  into `porelo/matrix/host-registration-token` in the account's config folder, `up` refuses with `matrix-token:` while a
  project naming that file finds it missing, and `down` removes both.

### Changed

- The person's forge login and `porelo-host-forge-password` come with every forge on a host, whether repositories are
  migrated into it or not; only the organization's `Owners` team waits for the repositories.
- The host's `/etc/hosts` stays out of the account's containers on every host, with its own forge or without one.

## [0.5.6] - 2026-10-28

### Removed

- Nothing of Tresorit is on a host any more: the role `drive`, the module `tresorit_installer`, the drive's step in
  `up` and `down`, and the stop's `drive` and `--email`, which `porelo-host-stop` now refuses with 64. `up` asks no
  drive login and `down` waits on no sync; a user's own drive is the interface's, outside the host's setup.

### Security

- `tresorit_installer` in 0.5.1 to 0.5.5 checked that the installer's signature covers the file from line 3 on, but
  ran the file from line 1, which it never checked: whoever controlled the download could put a command on line 1 and
  still pass every check. The module is gone with the drive; a host set up by those releases with a drive ran an
  installer checked that way.

### Changed

- The host's forge takes its certificate from the person's lasting CA, made once on their desktop with a name
  constraint, whose key never reaches a host: `up` makes a key and a request and names `forge-certificate` at the stop,
  `porelo-host-stop --request` prints the request, and the signed certificate comes back on standard input, checked
  before it is written. No CA key and no first password file are made on the host any more; the person's lasting
  password is set by `porelo-host-forge-password` from standard input, over ssh.
- The stop's secrets come on its standard input: `porelo-host-stop --stdin NEED...`, run as root over the admin's ssh,
  takes the vault's passphrase, the machine's keys, the host's VPN key and the central forge's token from the person's
  secrets file, one base64 line each, checks every line before using any, and pipes each value straight into its user.
  The drive holds no secret any more.
- `up`'s stop names `keys` with `vault-new` and `wireguard` while the host has no VPN key. `project` no longer puts
  keys from the drive into the vault; it refuses naming each key of the machine file the vault lacks.
- The host's VPN key lies in `/etc/wireguard/porelo-host.key`, root's with mode `0600`, so the VPN comes back after a
  reboot; `down` removes it. The AppArmor rule that let `wg` read the drive's key is gone.
- The host reads the machine file and the project's bundle from `/etc/porelo-host/setup/`, where the interface uploads
  them root's alone before `up`, no longer from the drive. `install` lets the account read them, `project` refuses
  them where anybody but root can write them, naming owner and mode, and `down` removes them.
- `up` refuses naming `forge-central-token` only while a repository is still to migrate, and the migration removes the
  token from `/run/porelo-host/` again. `forge_central_token_path` is gone.

## [0.5.5] - 2026-10-27

### Added

- The forge's runner takes `forge_runner_capacity` jobs at once, 4 by default, in place of one. `up` refuses a capacity
  whose jobs, with the VM pool, would take more than half the host's processors or memory, naming both sides.
- A job's `actions/cache` reaches the runner's cache on the forge's address, through two fixed ports published there,
  so a second run restores what the first saved instead of starting cold.

### Changed

- Each repository on the host's forge merges pull requests by fast-forward only, every other merge style off, and
  `up` reads the setting back. A merged pull request leaves its own commits on `main` unchanged; the forge no longer
  makes a merge commit authored by the person's forge account, which the pushed commits' check refused.

## [0.5.4] - 2026-10-27

### Added

- The host resolves `forge.porelo.internal` over loopback TLS and installs the Forgejo build reader. With repositories
  configured, the forge creates `porelo-<account>` in `gates`, pipes its token directly into Porelo's vault as
  `git.token.forge.porelo.internal`, and protects each `main` against direct pushes, requiring the person's approval
  and merge with no administrator override. A matching rule and existing vault entry stay unchanged across `up`;
  `down` removes the host's marked name mapping. Porelo's account's containers no longer copy the host's
  `/etc/hosts`, so tasks resolve the forge through Porelo's resolver alone.
- The forge gives the person an `operator` web login in the organization's `Owners` team, with a generated first
  password in root-only `/etc/porelo-host/forge/person.password` and a required password change at first sign-in.
  Existing accounts keep their passwords across `up`; `down` removes the first password file.
- The forge gives the person `porelo-host-push`, run with `sudo` on the host: it pushes each named repository's local
  `main` to its central forge without force, the central token asked for each time and kept nowhere. A central forge
  that moved refuses it; the command names the central commits, brings them to the local forge as `central/main`, and
  pushes none of the repositories after it. It trusts the central forge by the system's CAs, or by
  `porelo_host_forge_central_ca`, never by the host's own. `down` removes the command and its settings.

### Changed

- The README links the host lifecycle and the local forge's documentation.

## [0.5.3] - 2026-10-25

### Removed

- The forge no longer configures push mirrors to the central forge, since they force-push and can erase its commits.

### Added

- The forge gives configured agents their own accounts, repository write access and root-only token files kept across up.
- The forge's runner offers `ubuntu-24.04` and `ubuntu-26.04` labels on a pinned act image and fetches actions from
  github.com by their workflow pins. It sets the organization's Actions variables `PORELO_PUBLISH` to `false`,
  `PORELO_DEPLOY_PROFILE` to `forge-release` and `MAVEN_SNAPSHOTS_URL` to the forge's Maven registry, with a placeholder
  `JF_URL` and a placeholder `JF_ACCESS_TOKEN` secret created only when absent; every job's JDK trusts the host's CA
  through a read-only passwordless PKCS12 store set by `JAVA_TOOL_OPTIONS`; the runner offers the pinned Temurin 25 as
  `JAVA_HOME_25_X64`, as GitHub's image does.
- Fixed CPU, memory and process bounds for Forgejo, its runner daemon and jobs; `up` refuses accounts missing
  delegated controllers and VM pools that would use more than half the host's memory.
- The forge's CA is installed in Porelo's account for the broker and tasks, preserving the person's certificates;
  `down` removes the forge's trust from both files.
- The forge answers on port 443 of the host's loopback, for tasks, and of the VPN's address, through a root-owned
  socket that forwards to rootless Forgejo; its URLs carry `https://forge.porelo.internal/` with no port.

## [0.5.2] - 2026-10-24

### Added

- `porelo-host-stop` completes the host's drive login and vault step in the person's terminal, asking again after
  a failed attempt until it succeeds or the person cancels.

## [0.5.1] - 2026-10-24

### Changed

- `up` installs every agent Porelo's repository offers and starts no task, with no stop for a sign-in; `down` stops
  every running task of the account before clearing the vault.
- `porelo.host.lines`: a failed step's line carries the command's own words, a loop's by each failed item, cut to
  their tail; a task with `no_log` stays hidden.

### Added

- `porelo.host.lines`: a step's own words and usual duration on its `started` line, and one plan of the described
  steps across all plays before the run, leaving out steps whose conditions are false.
- A release made from a tag `v<version>` attaches the collection's tarball and a `SHA256SUMS` naming its digest; a tag
  that is not `galaxy.yml`'s plain version stops it before anything is attached.
- The collection `porelo.host`, built with `ansible-galaxy collection build` into a tarball that holds only what it
  ships; no role yet.
- The playbook `porelo.host.up`, run on the host itself with `-c local`, in two plays around the step only the person
  can take, and `porelo.host.down`, the order its steps come in.
- The stdout callback `porelo.host.lines`: one JSON line per step, and a waiting line naming what the person's step
  must give, for a program that runs the playbooks.
- The role `porelo.host.base`: the host's packages, KVM with libvirt and podman, stopping on a CPU without
  virtualization before it installs anything; and, once Porelo's setup made the account, that account in KVM's and
  libvirt's groups.
- The role `porelo.host.porelo`, everything through Porelo's own commands: Porelo installed by its pinned key with
  its setup script, `porelo setup`, a stop while the vault is missing or shut, the machine file's keys put into the
  vault and its project followed by its signature, every offered agent installed without starting a task or stopping
  for a sign-in; at `down`, every running task of the account stopped and the vault cleared.
- The role `porelo.host.forge`, where the host setting `porelo_host_forge` asks for it: Forgejo with its registry and
  its runner in rootless podman under accounts of their own, HTTPS on the VPN's address alone with a CA made on the
  host, the repositories `porelo_host_forge_repositories` names migrated once with push mirrors back, the person's
  token for the central forge read from their drive by the shell alone, and every build, an unreviewed task branch's
  too, publishing into the registry with the token of the account `porelo-publisher`, kept as the organization's
  Actions secret `PORELO_PUBLISHER_TOKEN` and never read out; stopped at `down`, keeping nothing.
- The role `porelo.host.vm_pool`, where the host setting `porelo_host_vm_pool` asks for it: one libvirt VM per run
  account from each system's cloud image by its pinned digest, its pool file mounted read-only into the forge
  runner's jobs and its run key kept on the host alone and handed to jobs as the forge organization's Actions secret
  `PORELO_POOL_SSH`, and each VM reverted on the host to its live base snapshot when `sudo porelo-pool-give-back`
  powers it off; at `down`, the secret and the VMs with their snapshots, disks, seeds, keys and file deleted.
- In `porelo.host.porelo`, the transports a project names and Matrix's homeserver installed through Porelo's setup
  script, enabling nothing.
