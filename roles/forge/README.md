# Role `forge`

The only script this role installs is `/usr/local/libexec/porelo/pre-receive`, mounted inside Forgejo.
Root's project operations belong to `/usr/sbin/porelo-host project`, and token issuance uses `forge issue-token`
and `forge lend-token`. Socket units call `porelo-host forge gate --web|--git|--runner --upstream <socket>`.
The push judge's socket unit runs `porelo-host judge-push` for each connection. The follow links repository hooks to
the installed pre-receive path.
Gate measurement uses `porelo-host forge measure --socket <socket> --host <host:port>` with optional `--requests`,
`--concurrency`, `--per-connection` and `--path`. Run it with a clean environment as an admitted person.

Project removal also deletes `/etc/porelo-host/matrix/<project>.admins` after checking its ownership and path, so
a removed project retains no Matrix room administration. See [Matrix access](../../doc/matrix.md).

The host's forge: Forgejo with its package registry in rootless podman under `porelo-forge`, serving HTTP on a
private Unix socket. The account's runtime directory `porelo-forge/` has mode `0700` and `http.sock` has mode `0600`;
keep-id maps the container's socket owner to the account. Forgejo publishes no TCP port and runs no SSH server.
The role runs when `porelo_host_forge` is true; `down` stops its gates and removes the forge. The runner has its own
account, `porelo-runner`, apart from the forge and every task.

Each push is judged when it arrives: Forgejo's container mounts the pre-receive hook
`/usr/local/libexec/porelo/pre-receive` and the directory `/run/porelo-host/verify` read-only. Its socket
`verify.sock` is the forge account's alone (`0600`) and listens before Forgejo starts; root's helper answers behind it. See [each push judged](../../doc/local-forge.md#each-push-judged-when-it-arrives).

The system sockets `/run/porelo-forge/web.sock` and `git.sock` are owned by the forge account and group
`porelo-people`, mode `0660`, inside a `0755` directory. Each connection needs the packaged gate as
the forge account through an `Accept=yes` socket unit. The gate reads the connected socket on fd 3 and removes all
caller-supplied `X-WEBAUTH-*` headers. It handles one request per connection, closes both sides, streams Git bodies,
and logs no requests. Unsupported transfer encodings, chunk extensions and trailers fail closed.

`web.sock` reads `SO_PEERCRED` and admits a login in `porelo-people` with uid at least 1000 and a supported login
shell. Root, service accounts with a non-login shell, unknown users and nonmembers receive `403`. Without
`Authorization`, the gate supplies that person's `X-WEBAUTH-USER`, except on `/v2`, `/api/packages` and Git's and
LFS's HTTP routes: those it never signs in, and without `Authorization` it answers `401` with a Basic challenge, or
`403` to a browser. It blocks all browser user settings and credential
reset routes, browser user administration and API token routes or user credential mutations. Reverse-proxy automatic
registration and reverse-proxy authentication for the API are disabled.

`git.sock` supplies no identity header and removes cookies. Its socket unit also listens on `127.0.0.1:<git_port>`
for Git on the host, with the same gate in the same git mode; the gate reads no peer there, and the web and runner
modes refuse a connection that is not a Unix socket. Without `Authorization`, it answers `401` with
`WWW-Authenticate: Basic`; Basic and token credentials pass to Forgejo, which checks their owner and rights.
Token issuance and task-token isolation belong to the host's token lifecycle. Tasks receive neither socket nor a
person's token. `/etc/porelo-host/forge.conf` records `host`, `name`, `port`, `git_port` and `account`, with no secret.
Root's administration helpers reach the private upstream socket; a person's forge calls use `git.sock`.

`up` creates no default forge user and removes an unrecorded `operator` login. Each person gets their own login
at admission. Browser access needs no password. The role removes the password helper, old HTTPS units and forge TLS
files; the person's sudoers configuration provides no password-setting command.

`up` retains `/etc/porelo-host/forge/central-ca.conf` (`0644`, holding `forge_central_ca`) as configuration for
`porelo-host project check-central <project> <repository>...`. The collection installs no gathered-push wrapper.
The packaged central check requires explicit repository names and is separate from the complete-project
`porelo-host project give-back-check` used before down.
APIs use `git.sock`; local Git uses `127.0.0.1:<git_port>`, a second listener of `porelo-forge-git.socket` with the
same token-only gate, since Git has no Unix-socket transport. Forgejo itself never listens on TCP, and the browser's
and the runner's gates serve their Unix sockets alone. Central transfers retain HTTPS and their CA. `up` removes the
sudoers drop-in an older host had for the push.

`porelo-host project add`, root's alone, registers an organization with an unlocked member in
`/etc/porelo-host/people/` (recording `member=<project> project-admin`) whom the applied organization in
`/etc/porelo-host/organization/applied.json` names as the project's admin, a signing key in Porelo's canonical
`ssh-ed25519 <base64>` signer format and a package-only publisher, or checks its commits against the central forge
before removing the project, dropping its memberships from `/etc/porelo-host/people/` and locking each person left with
none through the host program's person lifecycle. Its credentials stay in memory and Forgejo;
[project registration](../../doc/local-forge.md#registering-a-project)
describes the records, refusal checks and failure behavior. Down removes project records and legacy helpers.

The [resource bounds](../../doc/index.md) are set by `forge_cpus`, `forge_memory`, `forge_pids_limit`,
`forge_runner_cpus`, `forge_runner_memory` and `forge_runner_pids_limit`; job bounds use `forge_job_cpus`,
`forge_job_memory`, `forge_job_pids_limit` and `forge_job_omp_num_threads`. Their defaults and types are in
[`defaults/main.yml`](defaults/main.yml) and [`meta/argument_specs.yml`](meta/argument_specs.yml).

Unset `forge_runner_capacity`, `forge_job_cpus` and `forge_job_memory` fit the host's share for work beside the VM
pool, `porelo_host_work_share` percent of it (1 to 100; unset 50, half the host):
2 jobs when two minimum jobs fit, otherwise 1; then up to 4 CPUs and 8 GiB per job, with floors of 1 CPU and
768 MiB. Memory rounds down to whole MiB. A host with 16 processors and 32 GiB or more gets 2 jobs of 4 CPUs and
8 GiB when the VM pool fits the remaining budget. Explicit bounds stay unchanged; `forge_job_omp_num_threads`
defaults to the job's CPU quota. Before its configuration is written, the role
checks one budget with the VM pool: capacity × `forge_job_cpus` stays within the share of the host's processors, and
capacity × `forge_job_memory` plus the pool's VMs within the share of its `MemTotal`, so Forgejo, the runner and
Porelo's own tasks keep the rest. Above 50 the role writes a note saying so. A refusal names both sides and the
setting; the `capacity` entry point runs this check alone. A job's `actions/cache`
reaches the runner's cache on `127.0.0.1`, its server on `forge_runner_cache_port` (4000) and its proxy on
`forge_runner_cache_proxy_port` (4001), inside the shared container network namespace. No cache port is published.

The third gate socket, `/run/porelo-forge/runner.sock`, accepts Basic, token and Bearer credentials: no identity
header, cookies removed, and `401 Basic` without credentials, except the runner's own protocol under `/api/actions/`,
which Forgejo authenticates by the registration and runner tokens it carries. Its system socket unit uses the runner account's
primary group and mode `0660` in the existing `0755` directory. The runner account's
`forgejo-runner-proxy.container` mounts only this socket and runs two socat listeners on loopback at the web and Git
ports. Its image is pinned by digest. The proxy owns the network namespace; the runner depends on its service and
joins `container:forgejo-runner-proxy`, as do registration and every job. Registration uses
`http://127.0.0.1:<forge_http_port>`; existing registrations keep their token and move to that address.

Artifact v4 uploads and downloads are not passed by the runner gate. Their signed-URL blob transfers use
`/twirp/github.actions.results.api.v1.ArtifactService/UploadArtifact` and
`/twirp/github.actions.results.api.v1.ArtifactService/DownloadArtifact`, outside `/api/actions/`, without an
Authorization header. The gate returns `401` for those transfers; the `/api/actions/` exemption stays limited to
the runner protocol. Bearer-authenticated artifact control calls can pass, but do not make the blob transfers work.

Jobs get `/opt/porelo-host/runner-job-hosts`, owned by root, read-only as their `/etc/hosts`, and the host name
`localhost`. It maps `<host>.localhost` to `127.0.0.1`, so Forgejo's canonical URL, checkout and package registry reach
the token gate on loopback. Steps run as `uses: docker://…` get none of the runner's container options and see the
proxy's own `/etc/hosts`; all containers share its `/etc/resolv.conf`. A container's root can rewrite both for
later jobs until the proxy restarts. Jobs receive no gate socket or forge CA trust
mounts. External HTTPS uses each image's own certificate authorities.

The role pulls Forgejo's image, the runner's and the runner's proxy image, each pinned by version and digest in
[`vars/main.yml`](vars/main.yml). `forge_image_archives`, empty by default, names an absolute directory on the host
that holds some of them as OCI archives, each named `<digest>.tar` by the image's sha256 digest. Where it is set, the
role installs `skopeo`. Before the pull, an image's archive is checked: the directory and the archive must belong to
the account that runs `up`, writable by it alone, and the index must name the pinned digest alone, or `up` stops. If the account's podman lacks the image, skopeo copies it from a root-owned copy of the archive into
that account's storage under its pinned name and digest, and `up` stops unless podman then finds it by that digest. An
image whose archive is missing is pulled as before. `down` removes the accounts' storage, so each `up` loads again.
Molecule's Build uses this to run without the three registries.

Forgejo's `ROOT_URL` is `http://<host>.localhost:<forge_http_port>/`, with browser port `3000` by default.
`forge_git_port` defaults to `3001`. These are the person's local forwarded ports, not listeners on the host.
Porelo forwards them over SSH to the two sockets and sets Git remotes to the Git port because Forgejo renders clone
URLs from its browser URL alone. See the [gate access contract](../../doc/local-forge.md#socket-gates).

A build resolves from the registry with the organization's Actions secret `PORELO_PACKAGES_READ_TOKEN`, a `read:package`
token that can only read, and where the host has a VM pool, reaches it with `PORELO_POOL_SSH`, the pool's run key.
It publishes with `PORELO_PUBLISHER_TOKEN`, a `write:package`
token of the account `porelo-publisher`, whose team may write the organization's packages and nothing else; a run's
own token is refused there. The token is made inside Forgejo's container and never read out, so it stays with the
forge and the runner's jobs and reaches no task.

Registration gives each new organization the teams `developers`, `gates` and `agents`, and `forge_variables` and
`forge_placeholder_secrets`, where `{project}` in a value is the project's name; a migrated repository's `main` takes no
direct push, needs one approval from `Owners` or `developers`, and merges by fast-forward alone.

`forge_variables` defaults to `PORELO_PUBLISH: "false"`, `JF_URL: "https://jfrog.invalid"`, `PORELO_DEPLOY_PROFILE:
forge-release`, `MAVEN_SNAPSHOTS_URL`, the forge's own Maven registry, and `MAVEN_UPSTREAM_SNAPSHOTS_URL`, Sonatype's
snapshots, which a build reads without a token for the snapshots of other repositories; GitHub holds the same names
with its values.
`forge_placeholder_secrets` defaults to `[JF_ACCESS_TOKEN]`; missing secrets get `porelo-host-placeholder`,
and existing values are kept. Workflows differ between the forges only by variables and secrets.
