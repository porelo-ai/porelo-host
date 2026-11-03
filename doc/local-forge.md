# The local forge

## Socket gates

Forgejo serves HTTP over `/run/user/<forge uid>/porelo-forge/http.sock`, mode `0600` in a `0700` directory of its
account. It publishes no TCP port, certificate or SSH server. The system's `web.sock` and `git.sock` in
`/run/porelo-forge/` are owned by that account and `porelo-people`, mode `0660` in a `0755` directory. The Git gate
also listens on `127.0.0.1:<git_port>` for the host's own Git, described below.

Porelo forwards the browser's local web port over SSH to `web.sock`, at `http://<host>.localhost:<web_port>/`.
The gate takes the login from Unix peer credentials and `porelo-people` membership, removes supplied identity headers,
and signs the person in without a password when no Authorization header is present. Browser credential settings,
password reset and user-administration routes, and API token or password mutations are refused.

Every forge credential is made by the host, by Forgejo's CLI or Forgejo's own socket. On all three sockets the gate
refuses token routes, OAuth2 grants, account recovery, password changes and every runner management route, whatever
credential comes with the request. Forgejo's OAuth2 provider is off: its built-in applications would otherwise let a
signed-in person grant themselves a lasting token. The runners' own protocol under `/api/actions/` passes on
`runner.sock` alone, where the host's runner registers with a registration token from Forgejo's CLI. The gate
matches routes on the path's segments as Forgejo's router splits them, an encoded slash staying inside its segment.
A dot segment or an empty segment, also one behind an encoded slash, is refused with `400` before any match. So
are a bad escape, a decoded control character such as `%0a`, and an encoded slash beside a character a path does
not hold raw, such as `^` or `|`; Go then reads the path decoded, slash and all.

Forgejo signs a request in by the gate's `X-WEBAUTH-USER` for Git, LFS, packages and the container registry even
with `ENABLE_REVERSE_PROXY_AUTHENTICATION_API=false`. `web.sock` therefore passes `/v2`, `/api/packages` and Git's
and LFS's HTTP routes only with an Authorization header, never with the gate's sign-in. Package links under
`ROOT_URL`, the web port, lead clients there. Without a header the gate answers such a client `401` with a Basic
challenge, since Maven and pip send their token only once challenged. LFS object links carry the batch call's
header already. A browser, which sends `Sec-Fetch-*` headers, gets `403` instead and is never prompted for a
password. The container registry's `/v2/token` and Conan's
`authenticate` turn a token into a signed 24-hour token Forgejo keeps no record of, which a revocation does not end.
Every socket refuses them, so no job or person pushes a container image or a Conan package to the host's forge.
Container, npm, NuGet and other clients that send a Bearer token or their own header do not pass `git.sock`, which
takes Basic or `token` alone.

Git and API clients use `git.sock` with a token; on the host, Git, which has no Unix-socket transport, uses the
same gate on `127.0.0.1:<git_port>`, which `porelo-forge-git.socket` also listens on. The first unauthenticated Git request receives `401` and
`WWW-Authenticate: Basic`, so Git can ask its credential helper. The gate drops cookies and identity headers and
passes Basic or token Authorization to Forgejo. Porelo must set remotes to the local `git_port`; Forgejo's clone URLs
use its browser `ROOT_URL`. Tasks receive neither socket nor a person's token; their host task gate supplies the
task's token.

The runner uses a third system socket, `/run/porelo-forge/runner.sock`, owned by the forge account and the runner
account's primary group, mode `0660` in the same `0755` directory. It applies the same token-only rules as `git.sock`,
except for the runner's own protocol under `/api/actions/`, which Forgejo authenticates by the runner's tokens.
The runner account's `forgejo-runner-proxy.container` mounts only `runner.sock` and forwards two loopback listeners,
on the web and Git ports, to that socket. The runner starts after this proxy and is bound to it; its container,
registration container and jobs all join `container:forgejo-runner-proxy`.

Registration uses `http://127.0.0.1:<web_port>`. Jobs get a read-only `/etc/hosts` owned by root, which maps
`<host>.localhost` to `127.0.0.1`, so checkout and the package registry use the canonical forge URL with their tokens.
The Actions cache uses `127.0.0.1` on its existing ports, `4000` and `4001` by default, in this shared namespace.
Neither forge nor cache ports are published on the host. Jobs receive no forge socket or forge CA trust mounts.

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
provides `/usr/libexec/porelo/builds/forgejo`. The host keeps no lasting token for it or for the task gates. Each
task's gate pushes as `porelo-<login>`, a member of the project's `developers` team, with the token the host made for
that task at its start. The reader uses the person's own forge token. Tasks receive no forge socket; the host passes
their branch with the task token outside the container. No forge-specific `/etc/hosts` block is installed.

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

Root's organization follow registers projects named in the taken state and removes projects no longer named.
On a forge host it calls `porelo-host-project add <project> <admin> --signed-by 'ssh-ed25519 <base64>'` with an
unlocked project admin and that admin's current signing key from the state. The root helper remains available for
manual registration. Follow lends the helper its existing configuration lock through a validated inherited file
descriptor, so registration and removal stay inside the follow's exclusive lock.
The project name is 1 to 40 lowercase letters or digits, with hyphens allowed inside. The admin's user name must have
an unlocked plain root-only record `/etc/porelo-host/people/<admin>.conf` holding at least one membership, and an
existing forge login, and the [applied organization](#the-hosts-state-taken-from-the-organization) must name the
project for that admin. The signing key is the
project's SSH Ed25519 public key, in the form Porelo's `project.yml` uses in `signers`: one argument containing
`ssh-ed25519 <base64>`, with one space and no comment. Its canonical base64 decodes to the 51-byte SSH wire format:
the `ssh-ed25519` string header and a 32-byte public key. The bytes re-encode to exactly the supplied base64.
Registration pins the supplied key unchanged in `signed_by`; it does not follow a project or import its key.

The command creates the private organization named by the project, with the admin in its `Owners` team, and the
account `porelo-publisher-<project>`. Its `publishers` team writes that organization's packages only, with no code
access or repository creation. Its `write:package` token becomes the organization's Actions secret
`PORELO_PUBLISHER_TOKEN`. The generated password is discarded; no credential reaches stdout or a record.

`/etc/porelo-host/projects/<project>.conf`, root's with mode `0600`, holds `admin`, `signed_by` and `publisher` as
`key=value` lines, and registration adds `member=<project> project-admin` in fixed order to
`/etc/porelo-host/people/<admin>.conf`. Both record directories are root's with mode `0700`. An existing record,
organization, user or publisher name is refused before registration changes the forge. Success prints one compact JSON
line, in this field order:
`{"project":"<project>","admin":"<admin>","organization":"<project>","publisher":"porelo-publisher-<project>"}`.
The helper accepts no environment overrides for its paths or authority.

`porelo-host-project remove <project>` first lists every repository and package version. A project migrated by
refresh has a separate read-only deploy key for each migrated repository, under root's private
`/etc/porelo-host/organization/read/projects/<project>/`. Removal fetches every central ref with those keys and the
organization's pinned SSH host keys, then compares all commits reachable from local refs, including task branches
and tags. A missing read key, mismatched central address, unavailable forge or incomplete comparison prevents
removal before any deletion. Unpushed work keeps the project `held` in `org status`, naming its repositories and
commits; the next follow tries again. Memberships and member file access are revoked even while the forge is held.
The comparison pushes nothing and uses no central write token. Taking a project off deletes the host's private read
keys but not their public deploy keys at the central forge, as no central token is at hand then: they are read-only
and can no longer be used, and a person with admin rights on the central repository removes them by hand. Success's
JSON names each one in `left_at_central`, by address and title, and the follow writes that to its journal. Putting the
project on the same host again replaces that key.
Manual removal of a legacy registration without
read keys retains the gathered push's `--check` comparison and hidden central-token input.

Once the check passes, removal deletes the repositories and package versions, then the organization and publisher,
drops `member=<project> …` from every person record in `/etc/porelo-host/people/` and removes the project record.
The follow locks each person left with no membership. A private `removing=true`
record marks deletion after its preflight, so an interrupted run can finish a publisher or local cleanup after the
organization is gone. The read-key manifest is removed after its keys, so cleanup can resume too. Success prints
`{"project":"<project>","removed":true}`. Registration attempts cleanup of
its own new identities if an API operation fails. Deletion spans separate API operations; a failure after deletion
starts retains its progress and returns nonzero for the next follow to resume. `down` removes the helper and project records
with the forge.

Every refusal goes to stderr as `porelo-host-project: <words>`, with no success line on stdout. Its exit code is:

| Code | Meaning |
|---|---|
| `64` | Invalid input, including a malformed signing key or a missing or canceled central-token input |
| `65` | The records or forge refuse, including a taken name, a corrupt project record, an unknown project or unpushed commits |
| `69` | A needed dependency or setting is missing, unavailable or not root's, including a caller who is not root |
| `73` | A directory, record, temporary file or command output cannot be written or removed |

## Keeping a project's persons in step

`/usr/local/sbin/porelo-host-person` manages host people under the exclusive flock on `/etc/porelo-host/forge.conf`,
with the same refusal prefix (`porelo-host-person: <words>` on stderr) and exit codes (`64`, `65`, `69`, `73`). Root
calls `purge <user>`; who is on the host and who is locked changes only in the organization, and the host follows.

The follow takes each person's one current key from the applied organization. The account's GECOS field names `umask=0022`, which `pam_umask` reads ahead of `USERGROUPS_ENAB`'s `002`, so the
person's directories carry no group write; an account admitted before gets it on its next `add`. Once admitted, root
starts the person's user manager and runs `porelo setup` as the person with nothing on stdin, which registers the hooks
and starts `porelod` for good, so the tunnel's `porelod.sock` answers before the person's first task. A daemon that
does not start leaves the admission standing and says so on stderr: `porelo setup` as the person starts it.
Logins match `[a-z][a-z0-9-]{0,31}` and cannot be `porelo` or start with `porelo-`. A purged login is permanently
refused through root's mode `0600` `/etc/porelo-host/people/purged`, including on a later organization intake.

The follow reconciles each project's persons with the [state it took](#the-hosts-state-taken-from-the-organization):

1. A person record holds ordered `member=` lines, `locked=`, `ssh=` and `expires=`, with an optional `reason=` for
   a host, membership or key lock. Each admitted person's one card key replaces
   `/etc/ssh/authorized_keys/<login>`, with `expiry-time` when the card expires. There are no device names or VPN
   fields. `porelo-people` contains exactly the admitted logins that the host has not locked.
2. A project's lock, revocation, expired card or removal takes the person out of that project's memberships,
   forge teams and signers. Other memberships, the account, sessions and tokens stay. Where the host runs the gate
   and the project has no homeserver of its own, follow calls the gate's `keep-room` with exactly the unlocked
   members. Taking the project off drops the room after the project's forge removal succeeds; 75 retries on the next
   follow and 78 is named and left alone. While forge removal is held, the gate keeps the room with no members, retaining
   its conversation until removal succeeds.
   An unlocked membership restores that project's access. A host lock, the current key in the host KRL,
   organization revocation or removal of the last membership locks the account, ends sessions and deletes forge tokens.
   A project cannot undo a host lock.
3. Forgejo reconciliation uses its private socket API. Persons join `Owners` or `developers` by their role; gate and
   legacy agent identities join `developers`. Removal reaches every team in that organization and leaves other
   organizations alone. Even an unchanged commit reconciles access again, so a failed service change is retried at the
   next follow.

Each project's `/etc/porelo-host/signers/<project>.allowed` and `.certifiers` are root-owned mode `0644`, in a
mode `0755` directory. Porelo derives them from the taken state's signing keys: persons' Git signing keys in
`.allowed`, and task certificate authorities restricted to `task:<project>:*` in `.certifiers`. Porelo bounds
replaced keys by their validity periods. Locked or removed persons have no lines in that project. A task's
certificate names the one principal `task:<project>:<task>`, which the host and Porelo's
`task check-certificate` both hold it to at its start.

## The host's state taken from the organization

Root's `porelo-host-person org follow` fetches the signed organization from the central forge every five minutes;
`org refresh` follows immediately with empty stdin, and takes the host admin's central token on standard input to
add the organization's read key after setup or migrate projects waiting for that token. Setup supplies the initial
admin pin and organization deploy key; a taken state advances the pin. Project files are readable through
per-member ACLs, and membership loss locks an account for seven days before automatic purge. See the porelo role's README for the machine
file handover and host summary. `org pin` is unavailable.

The host's read key on the organization's repository is taken off by nobody. Porelo titles it by its fingerprint, so a
host set up anew adds its new key beside the old one, and a host set up anew or given up leaves its old key able to read
until the repository's owner removes it.

Each project and person entry is checked alone: a bad or duplicated project is named with state `refused` in the
answer's projects and left out while the rest applies; unusable person cards are named on stderr. A revoked key
stays revoked; a replacement card under another key can readmit the login. When the host card is signed by another
key Porelo accepted as the pinned key's successor, the pin moves to the person holding that key, a handover. `/etc/porelo-host/organization/applied.json` (`0600`) records the commit, the host
card, the projects, the persons and every revoked login; the persons' keys and revocations feed SSH's keys and the
KRL. An entry that names a login revoked counts even where its card is unusable for another fault, and its last key
stays recorded for the KRL.

The pin holds the machine's host admins first, then the keys of the organization's Organization Admins when `org fetch`
names them, so a host admin they replace is replaced at the next follow, with no step of the former admin's. The role
gets no account and no root here.

When an owner has replaced a host admin's card, no key the host holds signed that change, so every fetch is refused.
The way out is on the machine: root gives the host admins' keys, one `login key` line each, on standard input of
`porelo-host-person org renew-pin`, root's alone, which replaces the pin and the keys in the state taken, and answers as
`org status`. A host's own record refuses a rolled-back tip as well; to start over after a real rollback, root empties the
state directory of the unit `porelo-host-org-fetch`.

`porelo-host-person org status`, root's alone and read-only, answers the interface over root's SSH without it
reading root's files: `{"host":"<host>","refused":"<words>"|null,"commit":"<commit>"|null,"pinned":"SHA256:..."|null,"persons":[...]}`.
`refused` is what the last fetch refused, for the host admin to judge: the host keeps the state it took and does not read
this as being taken out of the organization, since a removal looks the same as a commit nobody allowed. Each
person, sorted by login, has `login`, `state`, `host_admin` (the organization names them a host admin) and `projects` (`project`, `role`). The
state is `active`, `locked`, `pending` (a lock or purge to retry), `purged`, or `named` for a login the applied
organization names that the host has not admitted; only `active` is an admission. It reads under the host's shared lock,
so it never sees a lock, removal or follow half done.

## Each push judged when it arrives

The first accepted push of a commit to the host's forge is its arrival, and there it is judged. Each repository of a
project's organization links `hooks/pre-receive.d/porelo` to the hook mounted read-only into Forgejo's container,
which runs it after Forgejo's own pre-receive hook: Forgejo 17 keeps its hooks in one directory its git's
`core.hooksPath` names (`/var/lib/gitea/home/hooks`), whose `pre-receive` runs Forgejo's check and then each
repository's `hooks/pre-receive.d`. The hook sends the push's lines, the repository and its quarantine
to `/run/porelo-verify/verify.sock` in the container, whose directory is the host's `/run/porelo-host/verify` mounted
read-only, and shows the answer to the pusher; no answer, or any answer but 200, refuses the push. A push that only
deletes refs brings no commit and passes unjudged.

Behind the socket, which only the forge account may connect to, root's `porelo-host-person verify-push` answers only
that account's peer. It maps the paths into the forge volume, refuses one outside the pushed repository, of an
organization no project registered or through a link on the way, and runs
`porelo commit verify --json` in a throwaway unit as the forge account, with no network and no home but that
repository read-only. Porelo gets the project's keys, each with its validity period (`--signers`), their
`cert-authority` lines for the project's own tasks (`--certifiers`), the KRL and each task certificate the host
recorded for the project and valid now, as `task --show` answers it (`--certificates`). Pushes are judged side by
side, each with its own staging directory; a follow waits for them and they for it. Every new commit, merges too, must be signed so that it holds now: by a person's key, by a task
certificate valid now, or by a task key whose recorded certificate holds now. Porelo's 65 refuses the push with its
lines; any other failure refuses it too.

Each accepted commit's verdict, with the arrival time Porelo read and the signer's fingerprint, is appended to root's
`/var/lib/porelo-host/arrivals/<project>/<repository>.jsonl` (0600). A person of the project reads it with
`sudo -n porelo-host-person arrivals <project> <repository>`. A verdict records what Porelo accepted when the push
arrived, not that the forge kept it: a push the forge refuses after both hooks leaves its verdict there, and the same
commit pushed again is judged again.

A repository's migration is not an arrival. The follow arms each repository: it links the hook first,
then records the history the repository holds as `migrated`, not judged here, since the central forge took those
commits, and last an `armed` line. A commit pushed between the link and the listing is judged and kept once. Only
later pushes are arrivals. A repository made on the forge another way is armed by the next follow, and is not judged
before; one whose history was not recorded is listed again at each follow until it is. The arming stops, recording
nothing, when the hook link names anything but the mounted hook, the mounted hook is not executable, a link stands
for the repository's hooks, Forgejo's shared `pre-receive` is missing or runs no repository's hooks, or a repository
names a `core.hooksPath` of its own. Removing the project takes its arrivals along, so a
project brought again under the name starts its record anew. A person reads the record under the same shared lock
the pushes take, never while a follow, a lock or a removal is half done.

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
SSH, naming the project and optionally the repositories in their order; a root call is refused with `77`:

    /usr/local/sbin/porelo-host-push porelo
    /usr/local/sbin/porelo-host-push porelo porelo-message-sluice

Without repository names it pushes every repository `porelo-host/push/<project>.conf` in the config folder names, in the config's
order; with names, those, refusing an unknown or duplicate name before asking for credentials. The config is read only
from the caller's `getent passwd` home (never `$HOME`): a plain file of theirs, not a link, mode `0600`, in a `0700`
directory of theirs, written by the host's follow, as that person, from the project's repositories on
the forge and their `original_url`; anything else is refused naming what was found. It reads local `main` with the
person's own local forge token from `sudo -n porelo-host-person forge-token`, which refuses a locked person or one
no project holds (a failed token request refuses with `69`), asks once on the terminal for their central forge write token without
showing it (`Token for the central forge (not shown): `) and keeps it only for the run, and pushes local `main` to each
repository's central address with a plain `git push` without force, the next only once the one before was taken. The
config's `central-ca` names the authority the central forge is trusted by (`porelo_host_forge_central_ca`, the system's
CA bundle by default). The local forge uses no TLS or CA. `up` installs `/usr/local/sbin/porelo-host-push`
(`0755`) and `/etc/porelo-host/forge/central-ca.conf` (`0644`); `down` removes them.

Every API request goes through `/run/porelo-forge/git.sock` to `http://localhost/api/v1/`, with the token header on a
pipe. Git has no HTTP Unix-socket transport, so local Git reaches the forge on `127.0.0.1:<git_port>`, a second
listener of `porelo-forge-git.socket` behind the same token-only gate: a request without a token gets `401` and
nothing reaches Forgejo, which itself never listens on TCP. Every process on the host reaches that port, so the token
is the bound; a rootless container with pasta's defaults does not reach the host's loopback, and runner jobs see the
runner proxy's own loopback. Git receives the local token as a header in its environment, never a URL or argument.
Central Git transfers still use HTTPS and the configured central CA.

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

`/usr/local/sbin/porelo-host-push --central <project>`, in a member's own account with no token, prints how each
repository's approved `main` stands against the central forge, as one JSON object with `project`, `read_at` and
`repositories`. Each repository's `state` is `ahead` with `commits`, `up-to-date`, `moved-on` (the central forge moved on
or the two went apart, so a push would be refused), or `cannot-say` with `why`: `no-read-key`, `unreachable`,
`no-central-main` or `local`. No repositories at all means the host could not say. The follow reads it with the
repository's read key by `git ls-remote`, clones nothing, and writes `/etc/porelo-host/organization/central/<project>.json`
with a read ACL for each unlocked member, so the answer can be five minutes old, and longer when a follow fails. With no
answer the account may read it refuses with 69. The push itself still decides.

The gathered push asks for the central token with hidden input in the SSH terminal and stores it nowhere; git
receives it only as a header in its environment, never on a command line, and the command's output names no token. The
token for a project's initial repository migration arrives only on `org refresh` standard input. A project stands
as `waiting-for-token` until it arrives. Refresh passes it once to the root project helper on a pipe; the helper adds
a read-only deploy key to the central repository and migrates the repository the organization state names through
Forgejo's private socket API, with the token in the request body alone. HTTPS and git SSH project addresses are
normalized to the central forge's HTTPS clone address. The central forge must match the organization's adapter
settings, which this helper reads as an indented `repository:` setting, optionally single- or double-quoted; other spellings are refused before
sending the token. An existing matching migration and deploy key are kept on retry. The key's title is
`porelo host <host> project <project>`. A read-only key of exactly that title with another public half was this host's
before, and the token that adds the new key deletes it; one with write access is refused and kept. A key of another host
stays, since that host may still hold the project for unpushed work and compare with it, and so does one titled
`porelo-host-<project>`, as earlier versions made it, which names no host. The repository's owner removes those. A
refusal stands as the project's `why` in `org status` until a later try ends, in the helper's last line and with its
exit code, and reaches the journal; its other output never does. The follow then writes members'
push configs from Forgejo's repositories and their `original_url`. At each follow the host also reads the project's signed file: the
helper asks for the project's own central `main` with its read key, makes a bare copy that only the forge's account can read if that
commit or the signers changed, and an isolated `porelo project verify` with no network answers from that copy. The file's
`repositories.<name>.central` names what else is taken: with the token at hand, all of them in the same follow, each
with its own read key. One named later waits for a token and says so; one refused is named in `why`, and the rest go on;
one taken out of the file stays with its work. The forge names each after its central repository. Each `main` needs one
approval by another person after which a push dismisses it, unless `repositories.<name>.review` or `project.review` is
`optional`, when the author may merge their own. Either way nobody pushes straight to `main`, and only owners and
developers merge. A rule changed by hand is set back at the next follow; a file that cannot be read keeps the last values.
Removing a project deletes its local
private read keys; the recorded address retains an explicit SSH port for the removal comparison. The repository name
`repositories.json` is reserved for the read-key manifest. Public deploy-key registrations on the central forge require separate removal with central
administrative authority. `/usr/local/sbin/porelo-host-push --pull <project> [repositories...]` brings central `main` locally as
`central/main`, in the person's own account with the central token on stdin. Local `main` reaches it by a pull
request. The project's own repository is the exception, as tasks read `project.yml` there: once Porelo's `project verify`
has accepted central's file, the follow brings local `main` up to that commit, only forward and with no hook or branch
rule, as `main` stays closed to every push. If local `main` holds commits central lacks, it stays, and `org status`'s
`why` says a task here reads an older project file, until a gathered push or a person's pull request joins them.
A repository's address on the host is `http://127.0.0.1:<git_port>/<project>/<name>.git`, with `git_port` from the host
card and `<name>` the repository's name at the central forge; a project's `upstream` names it and its `central` the other. Push and pull each call `sudo -n porelo-host-person forge-token` for the local token and put it into the
person's vault as `<forge>.person`, since it replaces the one there.
No token for the central forge lies on the host.

## If the host is lost

Work that exists only on the host is lost with it: task branches, accepted local `main` commits not sent centrally,
local build records and local registry snapshots. A green local build or a local merge does not put that work on the
central forge.

`down` removes the forge's volumes and credentials and the pool's VMs, snapshots and keys. It stops tasks but leaves
their containers and workspaces on the host, then clears the vault. None of these teardown roles exports the local
forge, its registry or task workspaces anywhere. Preserve local-only work before teardown.
