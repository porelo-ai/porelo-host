# The local forge

## Socket gates

Forgejo serves HTTP over `/run/user/<forge uid>/porelo-forge/http.sock`, mode `0600` in a `0700` directory of its
account. It publishes no TCP port, certificate or SSH server. The system's `web.sock` and `git.sock` in
`/run/porelo-forge/` are owned by that account and `porelo-people`, mode `0660` in a `0755` directory.

Porelo forwards the browser's local web port over SSH to `web.sock`, at `http://<host>.localhost:<web_port>/`.
The gate takes the login from Unix peer credentials and `porelo-people` membership, removes supplied identity headers,
and signs the person in without a password when no Authorization header is present. Browser credential settings,
password reset and user-administration routes, and API token or password mutations are refused.

Git and API clients use `git.sock` with a token. The first unauthenticated Git request receives `401` and
`WWW-Authenticate: Basic`, so Git can ask its credential helper. The gate drops cookies and identity headers and
passes Basic or token Authorization to Forgejo. Porelo must set remotes to the local `git_port`; Forgejo's clone URLs
use its browser `ROOT_URL`. Tasks receive neither socket nor a person's token; their host task gate supplies the
task's token.

The runner uses a third system socket, `/run/porelo-forge/runner.sock`, owned by the forge account and the runner
account's primary group, mode `0660` in the same `0755` directory. It applies the same token-only rules as `git.sock`.
The runner account's `forgejo-runner-proxy.container` mounts only `runner.sock` and forwards two loopback listeners,
on the web and Git ports, to that socket. The runner starts after and requires this proxy; its container,
registration container and jobs all join `container:forgejo-runner-proxy`.

Registration uses `http://127.0.0.1:<web_port>`. Jobs get `--add-host=<host>.localhost:127.0.0.1`, so checkout and the
package registry use the canonical forge URL with their tokens. The Actions cache uses `127.0.0.1` on its existing
ports, `4000` and `4001` by default, in this shared namespace. Neither forge nor cache ports are published on the
host's VPN address. Jobs receive no forge socket or forge CA trust mounts.

The local forge is the host's private Forgejo: it holds task branches, runs independent builds and supplies snapshots
through its local registry. The central forge holds the work the person sends outward and runs the central publication
workflows. These are separate destinations, with separate credentials.

![Task branches are built on the local forge, merged by the person, and sent to the central forge by a gathered push; central changes return through central/main](images/local-forge.svg)

A traffic cone marks a step not built yet.

This arrangement uses a project whose security class is `online` and whose repositories name the local forge as their
immediate Git destination. The literal project-file key is `upstream`: here it means the local forge, even though the
central forge is the destination of the gathered push. See Porelo's [project
file](https://github.com/porelo-ai/porelo/blob/main/doc/project-file.md) for the schema and [security
boundary](https://github.com/porelo-ai/porelo/blob/main/doc/security.md) for what the gate permits when the task pushes.

## Task branches and the local build

An `online` task pushes through its gate to `porelo/<task>` on the local forge immediately. The host lends the Git
credential; the task holds no credential for that Git destination. A refusal by the local forge fails the task's push.
The branch is where the person can review the work in a pull request.

The local build runs on the forge's runner, independently of checks the agent runs inside the task. The repository's
workflow determines its triggers and checks. A repository's workflow must run on task-branch pushes or pull requests
before there is a local build to review.

The forge is off by default. The host setting `porelo_host_forge: true` turns on Forgejo, its registry and its runner.
Forgejo Actions is enabled by the role. The forge and runner use separate system accounts and rootless containers, apart
from Porelo's account. Their resource bounds are in the [host lifecycle](index.md).

A VM pool is optional. Defining `porelo_host_vm_pool` turns it on, with `systems` chosen from `ubuntu` and `fedora`, and
`accounts` from 1 to 8 for each system. It requires the forge and gives each run account a VM of its own. Without that
setting, no pool is made; a runner job does not need a VM unless its workflow asks for one.

Where the pool exists, jobs receive its description read-only at `/etc/porelo-host/pool/pool.json` and its run key as
the Actions secret `PORELO_POOL_SSH`. The pool supports `porelo-machines acceptance --pool`. Giving a VM back powers it
off; the host reverts its base snapshot so a run's changes do not reach the next run. See the [pool
role](https://github.com/porelo-ai/porelo-host/blob/main/roles/vm_pool/README.md) for its contract.

Porelo reads build verdicts and failed-job logs through the `forgejo` build reader on the host, outside every task, and
delivers them into the task's `/porelo/files`. Where the forge is enabled, `up` installs `porelo-adapter-forgejo`, which
provides `/usr/libexec/porelo/builds/forgejo`. With repositories configured, it creates `porelo-<account>`, where
`forge_porelo_account` defaults to `porelo_host_account`, in the organization's `gates` team. That team writes code and
pull requests and reads Actions on every repository. Its generated token is piped directly into the account's vault as
`git.token.forge.porelo.internal`, only while that entry is missing; no token file is written. The gate and build reader
use their token through the host's Git gate. Tasks receive no forge socket; the host passes their branch with the
task token outside the container. No forge-specific `/etc/hosts` block is installed.

The reader receives its credential from the vault for each call, independently of any task access to declared services.
The project's build configuration names `forge: forgejo` and a token credential, with its API transport reaching
`git.sock`; see the [adapter
documentation](https://github.com/porelo-ai/porelo-adapters/blob/main/doc/index.md#forgejo-actions) and Porelo's
[build-reader contract](https://github.com/porelo-ai/porelo/blob/main/doc/build-readers.md).

## The local registry and publication settings

The local registry lets repositories resolve each other's snapshots without first publishing them outward. With
repositories configured, `up` creates a package-only publisher account, supplies its token as an organization Actions
secret and sets the local Actions variables below. The central values are what the central forge's workflows read; `up`
sets the local forge's values only.

| Variable or secret | Local forge, set by `up` | Central forge configuration |
|---|---|---|
| `vars.PORELO_PUBLISH` | `false` | `true` |
| `vars.PORELO_DEPLOY_PROFILE` | `forge-release` | `central-sonatype-release` |
| `vars.MAVEN_SNAPSHOTS_URL` | Forge Maven URL below | [Sonatype snapshots][snapshots] |
| `secrets.PORELO_PUBLISHER_TOKEN` | The local publisher's package token; private registry reads need authentication too | A placeholder for anonymous Sonatype snapshot reads; central deployment uses its own credentials |
| `vars.JF_URL` | `https://jfrog.invalid`, a placeholder: the variables API takes no empty value, and no real service answers it | The Artifactory instance that `PORELO_PUBLISH` uploads go to |
| `secrets.JF_ACCESS_TOKEN` | `porelo-host-placeholder`, created only when the secret is absent; an existing value is kept | The Artifactory access token for those uploads |

[snapshots]: https://central.sonatype.com/repository/maven-snapshots/

The default organization is `porelo`. The forge's browser address is `http://<host>.localhost:<web_port>/`.
The Forge Maven URL is `http://<host>.localhost:<web_port>/api/packages/<forge_owner>/maven`.
Registry clients in jobs use the shared loopback proxy with token authentication. External HTTPS uses the job image's
own certificate authorities; no forge CA bundle or JVM trust store is injected.

The organization and its repositories are private, so a step that fetches again after a checkout without credentials
fails, where GitHub's public repository needs none.

**`PORELO_PUBLISH=false` still deploys snapshots to the forge's registry** when the workflow's deploy conditions hold.
`PORELO_DEPLOY_PROFILE` selects that destination. For example, the buildtools workflow deploys on `main` pushes and
version tags; its deployment job is not switched off by `PORELO_PUBLISH`. Registry credentials also allow a workflow to
publish a task branch's snapshot, but do not make every task-branch push deploy one.

`PORELO_PUBLISH=false` skips the outward publication and central-only jobs that workflows guard with that variable, such
as Artifactory uploads and deleting central workflow runs. In buildtools it also skips rebuilding the machine snapshots
used by the machine provider. It does not disable the local build or every artifact upload. The same variable names on
both forges let workflows select their destinations without editing the workflow between them.

## Registering a project

With the forge running, root registers a project through
`porelo-host-project add <project> <admin> --signed-by 'ssh-ed25519 <base64>'`.
The project name is 1 to 40 lowercase letters or digits, with hyphens allowed inside. The admin's user name must have
an unlocked plain root-only record `/etc/porelo-host/people/<admin>.conf` holding at least one membership, and an
existing forge login, and the [applied registry](#the-hosts-state-taken-from-the-registry) must name the project for
that admin. The signing key is the
project's SSH Ed25519 public key, in the form Porelo's `project.yml` uses in `signers`: one argument containing
`ssh-ed25519 <base64>`, with one space and no comment. Its canonical base64 decodes to the 51-byte SSH wire format:
the `ssh-ed25519` string header and a 32-byte public key. The bytes re-encode to exactly the supplied base64.
Registration pins the supplied key unchanged in `signed_by`; it does not follow a project or import its key.

The command creates the private organization named by the project, with the admin in its `Owners` team, and the
account `porelo-publisher-<project>`. Its `publishers` team writes that organization's packages only, with no code
access or repository creation. Its `write:package` token becomes the organization's Actions secret
`PORELO_PUBLISHER_TOKEN`. The generated password is discarded; no credential reaches stdout or a record.

`/etc/porelo-host/projects/<project>.conf`, root's with mode `0600`, holds `admin`, `signed_by` and `publisher` as
`key=value` lines (and, once `porelo-host-person sync` has run, `commit`, `access_commit` and one `signer` line per
verified project signing key), and registration adds `member=<project> project-admin` in fixed order to
`/etc/porelo-host/people/<admin>.conf`. Both record directories are root's with mode `0700`. An existing record,
organization, user or publisher name is refused before registration changes the forge. Success prints one compact JSON
line, in this field order:
`{"project":"<project>","admin":"<admin>","organization":"<project>","publisher":"porelo-publisher-<project>"}`.
The helper accepts no environment overrides for its paths or authority.

`porelo-host-project remove <project>` first lists every repository and package version. For repositories, it calls
the gathered push's read-only `--check <project> <repositories...>` mode, asking for the central token with hidden
input. `--check` reads each repository's central `https://` `original_url` kept by Forgejo from its migration through
the admin API and trusts the central forge by `/etc/porelo-host/forge/central-ca.conf` (the system CA bundle
`/etc/ssl/certs/ca-certificates.crt` unless `porelo_host_forge_central_ca` names another); a repository without an
`original_url` is refused by name. Every commit reachable from a local ref, including task branches and tags, must be
reachable from a central ref. Missing settings, an unreachable forge or unpushed commits refuse removal before any
deletion; the comparison pushes nothing.

Once the check passes, removal deletes the repositories and package versions, then the organization and publisher,
drops `member=<project> …` from every person record in `/etc/porelo-host/people/` and removes the project record, and
locks each unlocked person left with no membership through `porelo-host-person lock`. Success prints
`{"project":"<project>","removed":true,"locked":[<users>]}`. Registration attempts cleanup of
its own new identities if an API operation fails. Deletion spans separate API operations; a failure after deletion
starts can leave part of the project removed, with its record retained and a nonzero exit. Keep the project idle
while removing it so a concurrent push cannot add work after the check. `down` removes the helper and project records
with the forge.

Every refusal goes to stderr as `porelo-host-project: <words>`, with no success line on stdout. Its exit code is:

| Code | Meaning |
|---|---|
| `64` | Invalid input, including a malformed signing key or a missing or canceled central-token input |
| `65` | The records or forge refuse, including a taken name, a corrupt project record, an unknown project or unpushed commits |
| `69` | A needed dependency or setting is missing, unavailable or not root's, including a caller who is not root |
| `73` | A directory, record, temporary file or command output cannot be written or removed |

## Keeping a project's developers in step

`/usr/local/sbin/porelo-host-person` manages host people under the exclusive flock on `/etc/porelo-host/forge.conf`,
with the same refusal prefix (`porelo-host-person: <words>` on stderr) and exit codes (`64`, `65`, `69`, `73`). Root
calls `add <user> --role project-admin` (recording `member=hand`), `lock <user>` and `purge <user>`. Either root or the
project's unlocked recorded admin (`sudo -n /usr/local/sbin/porelo-host-person sync <project>`, permitted to
`%porelo-people` in `/etc/sudoers.d/porelo-host-person` and checked by the helper against `SUDO_USER` and `admin=` in
`/etc/porelo-host/projects/<project>.conf`) calls `sync <project>`.

`porelo-host-person sync <project>` reconciles the project's developers with its signed bundles, once the
[applied registry](#the-hosts-state-taken-from-the-registry) names the project for its recorded admin:

1. Root traverses `<admin home>/.local/share/porelo-host/setup/<project>/` without following symlinks, requires
   `project.bundle` and `access.bundle` to be plain files owned by the admin and not writable by group or others, and
   copies both into a fresh `0700` root-only directory under `/run/porelo-host/sync/`, removed before `sync` exits.
2. Root runs `porelo project verify --json` through `systemd-run --pipe --wait --quiet --collect` in transient unit
   `porelo-host-sync-<project>` with `DynamicUser=yes`, `PrivateNetwork=yes`, `ProtectHome=yes` and `LoadCredential=`
   for both copied bundles. Verification pins `signed_by=` from the project record on the first run and the recorded
   `signer=` keys thereafter, passing `--since` and `--access-since` once commits are recorded. A nonzero exit refuses
   with `65` and Porelo's stderr words.
3. `access.yml`'s `host:` block must match this host's VPN `network`, live `wg-porelo` `wireguard_public_key` and
   `ca_sha256` (the 64-digit lowercase hex SHA-256 of the DER certificate in `/etc/porelo-host/forge/ca.pem`), or
   `sync` refuses (`65`) naming every differing field.
4. When both verified commit IDs equal the project record's `commit=` and `access_commit=`, `sync` changes nothing and
   answers with `"unchanged":true`. Otherwise it checks the entire diff against `/etc/porelo-host/people/`, host
   accounts and groups before changing anything: an invalid user name, a system or unrecorded account, an existing
   group name for a new user, a locked person listed again (who must be purged first), or an SSH key, WireGuard key or
   VPN address outside the network, reserved or held by another person refuses the whole run (`65`) naming every
   offending entry. `forge_login` in the verified JSON is ignored; the person's host login is their local forge login.
5. Unchanged laptops keep their recorded names; newly added laptops receive the lowest free `l1`, `l2`, … name on that
   person's record. A listed developer with no record is admitted with `member=<project> developer` (host account,
   VPN-restricted SSH keys, WireGuard peers, local forge identities and Matrix machine token). An existing unlocked
   person receives `member=<project> developer` without a second account, with added laptops admitted and dropped
   laptops removed individually from `/etc/ssh/authorized_keys/<user>` and WireGuard. A person no longer listed loses
   `member=<project> developer` and is locked only when no membership remains; `member=hand` and
   `member=<project> project-admin` are never changed by `sync`.
6. The organization's `developers` team on the local forge is brought to the listed developers' host logins; if that
   team is missing, `sync` refuses (`65`) naming `developers` and `"run bring first"` before changing people or records.
7. `/etc/porelo-host/projects/<project>.conf` is updated atomically with `commit=`, `access_commit=` and the verified
   `signer=` lines, and stdout prints one compact JSON line:
   `{"project":"<project>","commit":"<commit>","access_commit":"<access_commit>","added":[...],"dropped":[...],"laptops_added":["<user>/<laptop>",...],"laptops_dropped":["<user>/<laptop>",...],"unchanged":false}`.

## The host's state taken from the registry

The host takes which projects it has, and for whom, from the signed registry state its host admin brings, never from
the central forge. Root pins the host admin once, at setup, with the key that signed the host card:
`porelo-host-person registry pin <login> "ssh-ed25519 <base64>"` writes `/etc/porelo-host/registry/pin.conf` (`0600`,
`admin=` and `key=`, in a `0700` directory) and refuses a second pin.

The host admin's Porelo uploads `registry.bundle` into `~/.local/share/porelo-host/setup/`, and root or the pinned host
admin (`sudo -n /usr/local/sbin/porelo-host-person registry`, the sudoers rule's bare form alone) runs `registry`. Root
copies the bundle as `sync` does and runs `porelo registry verify --repository <copy> --host <host> --pinned
<fingerprint> --json` in the transient unit `porelo-host-registry`, isolated like the sync's, with `--since` and the
applied commit once one is applied; `<host>` is `forge.conf`'s `host=`. A refusal from Porelo, a bundle signed by
another key or one not descending from the applied state alike, refuses the whole bundle with `65` and changes nothing,
so no lock, revocation or handover is rolled back.

Each project and person entry is checked alone: a bad or duplicated one is named in the answer's `refused` and left
out while the rest applies. A login once applied as revoked stays revoked; a later entry admitting it again is refused
alone. When the host card is signed by another key Porelo accepted as the pinned key's successor, the pin moves to the
person holding that key, a handover. `/etc/porelo-host/registry/applied.json` (`0600`) records the commit, the host
card, the projects, the persons and every revoked login; the persons' keys and revocations are for SSH's keys and the
KRL to read, which this step does not write. A project registered here that the registry no longer names for its
recorded admin is named in `dropped` and kept: its next `sync` and a new `porelo-host-project add` for it are refused
(`65`) until the host admin removes it or names it again. A revoked login stays revoked: an entry that names it
revoked counts even where it is refused for another fault, its last key stays recorded for the KRL, and a revoked admin
gets no project, no `sync` and no `add`. A host card without its signer refuses the bundle (`69`), and `registry pin`
runs as root alone, never through `sudo`. Success prints
`{"commit":"<commit>","pinned":"SHA256:...","projects":[...],"dropped":[...],"revoked":[...],"refused":[...],"unchanged":false}`.

## The person's two decisions

**First, accept the work by merging `porelo/<task>` into local `main`.** The person reads the pull request and its local
build before merging in Forgejo. On every configured repository, local `main` is protected: direct pushes are disabled,
one approval is required, and only members of `Owners` or `developers` can supply the counted
approval and merge the pull request. Administrator merge overrides are disabled. The pull request reaches `main` by
fast-forward only, so its own commits arrive unchanged and the forge adds no commit of its own. Status checks are not
required; the
person reads the build before approving. Repeating `up` keeps a matching protection rule and corrects different
settings.

The blue arrows in the picture place forge observation on the host. Build reading works; the additional review and
lifecycle steps are not built:

- Start a reviewer after a green build: not built yet.
- Run a task in the reviewer role: not built yet.
- Read pull-request comments, send replies and wake the developer task: not built yet.
- End the task after the person merges its pull request: not built yet.

**Second, start a gathered push of accepted local `main` to the central forge.** This is a separate decision about
sending the merged work outward. Any developer or admin of the project runs it in their own account on the host over
SSH, never as root and never through `sudo` (root is refused with `77`), naming the project and optionally the
repositories in their order:

    porelo-host-push porelo
    porelo-host-push porelo porelo-message-sluice

Without repository names it pushes every repository `~/.config/porelo-host/push/<project>.conf` names, in the config's
order; with names, those, refusing an unknown or duplicate name before asking for credentials. The config is read only
from the caller's `getent passwd` home (never `$HOME`): a plain file of theirs, not a link, mode `0600`, in a `0700`
directory of theirs, written by `porelo.host.bring` and `porelo.host.join` from the repositories the person reaches on
the forge and their `original_url`; anything else is refused naming what was found. It reads local `main` with the
person's own local forge token `<forge_name>.person` from their vault (a missing entry refuses with `69`, naming the
entry and `porelo-host-stop --stdin identities`), asks once on the terminal for their central forge write token without
showing it (`Token for the central forge (not shown): `) and keeps it only for the run, and pushes local `main` to each
repository's central address with a plain `git push` without force, the next only once the one before was taken. The
config's `central-ca` names the authority the central forge is trusted by (`porelo_host_forge_central_ca`, the system's
CA bundle by default), never the host's own CA unless configured so. `up` installs `/usr/local/sbin/porelo-host-push`
(`0755`) and `/etc/porelo-host/forge/central-ca.conf` (`0644`), and `down` removes both.

When central `main` holds commits local `main` lacks, the push is refused and nothing is lost on either forge. The
command names those commits and brings central `main` to the local forge as the branch `central/main`. A task joins
them on a branch of its own: it starts from `central/main` and merges local `main` into it with a commit worded by the
shared rule on commit messages. That branch receives a local build and the person's merge decision, and local `main`
reaches it by fast-forward, before the person runs the push again. The repositories named after a refused one are not pushed, and the command says which.
Starting that merge task automatically is not built.

## Credentials belong to their destination

Each name in `porelo_host_forge_agents` gets its own local forge account, `agent-<name>`, when repositories are
configured. Its team can write the organization's code, pull requests and issues, and read actions and packages; it
cannot create repositories. Its token is written into `/etc/porelo-host/forge/agents/<name>.token`, owned by root, mode
`0600`, in a `0700` directory. An existing file is kept across `up`; removing an inventory name does not delete the
account or token. These accounts carry no authority to write to the central forge.

An agent's push starts the workflows' `push` and `pull_request` runs, but the forge refuses it a `workflow_dispatch`
(`403`), since the team only reads Actions. Its token also reads no job's log (`404` through the API), no push mirror
(`403`) and not its own user (`403`, no `read:user` scope).

Each admitted person's web login is their own account name. In a project they own or join they belong to its
`Owners` or `developers` team. Their browser reaches the forge through the [web gate](#socket-gates), which derives
their login from the host account. There is no forge certificate exchange or password-setting helper.

The registry publisher is a separate account. Its package token stays with Forgejo and runner jobs as
`PORELO_PUBLISHER_TOKEN`; it is not handed to tasks. The host build reader's credential and a task's declared service
credentials have their own routes, described in [Porelo's credential
documentation](https://github.com/porelo-ai/porelo/blob/main/doc/credentials.md).

The gathered push asks for the central token with hidden input in the SSH terminal and stores it nowhere; git
receives it only as a header in its environment, never on a command line, and the command's output names no token. The
token for the initial repository migration is used the same way, once: a `bring` with a repository still to migrate
lists it in `~/.config/porelo-host/push/<project>.migrate` (no secret) and waits, naming `forge-central-token`; the
person's stop pipes the token into `porelo-host-push --migrate <project>`, which has Forgejo migrate each listed
repository it lacks, with the token in the request body on a pipe alone, and removes the list; the `bring` run again
goes on. `porelo-host-push --pull <project> [repositories...]` brings central `main` to the local forge as
`central/main` with the same token on standard input; local `main` is protected and reaches it by a pull request. No
token for the central forge lies on the host.

## If the host is lost

Work that exists only on the host is lost with it: task branches, accepted local `main` commits not sent centrally,
local build records and local registry snapshots. A green local build or a local merge does not put that work on the
central forge.

`down` removes the forge's volumes and credentials and the pool's VMs, snapshots and keys. It stops tasks but leaves
their containers and workspaces on the host, then clears the vault. None of these teardown roles exports the local
forge, its registry or task workspaces anywhere. Preserve local-only work before teardown.
