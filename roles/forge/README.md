# Role `forge`

Project removal also deletes `/etc/porelo-host/matrix/<project>.admins` after checking its ownership and path, so
a removed project retains no Matrix room administration. See [Matrix access](../../doc/matrix.md).

The host's forge: Forgejo with its package registry in rootless podman under `porelo-forge`, serving HTTP on a
private Unix socket. The account's runtime directory `porelo-forge/` has mode `0700` and `http.sock` has mode `0600`;
keep-id maps the container's socket owner to the account. Forgejo publishes no TCP port and runs no SSH server.
The role runs when `porelo_host_forge` is true; `down` stops its gates and removes the forge. The runner has its own
account, `porelo-runner`, apart from the forge and every task.

The system sockets `/run/porelo-forge/web.sock` and `git.sock` are owned by the forge account and group
`porelo-people`, mode `0660`, inside a `0755` directory. Each connection starts the Python standard-library gate as
the forge account through an `Accept=yes` socket unit. The gate reads the connected socket on fd 3 and removes all
caller-supplied `X-WEBAUTH-*` headers. It handles one request per connection, closes both sides, streams Git bodies,
and logs no requests. Unsupported transfer encodings, chunk extensions and trailers fail closed.

`web.sock` reads `SO_PEERCRED` and admits a login in `porelo-people` with uid at least 1000 and a supported login
shell. Root, service accounts with a non-login shell, unknown users and nonmembers receive `403`. Without
`Authorization`, the gate supplies that person's `X-WEBAUTH-USER`. It blocks all browser user settings and credential
reset routes, browser user administration and API token routes or user credential mutations. Reverse-proxy automatic
registration and reverse-proxy authentication for the API are disabled.

`git.sock` supplies no identity header and removes cookies. Without `Authorization`, it answers `401` with
`WWW-Authenticate: Basic`; Basic and token credentials pass to Forgejo, which checks their owner and rights.
Token issuance and task-token isolation belong to the host's token lifecycle. Tasks receive neither socket nor a
person's token. `/etc/porelo-host/forge.conf` records `host`, `name`, `port`, `git_port` and `account`, with no secret.
Root's administration helpers reach the private upstream socket; a person's bring and join use `git.sock`.

`up` creates no default forge user and removes an unrecorded `operator` login. Each person gets their own login
at admission. Browser access needs no password. The role removes the password helper, old HTTPS units and forge TLS
files; the person's sudoers configuration provides no password-setting command. Porelo's account setup removes its
forge CA trust block and task CA file.

`up` prepares the forge without repositories (`forge_repositories` stays empty on the host) and installs
`/usr/local/sbin/porelo-host-push` (`0755`, push and `--pull` through `sudo -n` for a current project developer,
reading `~/.config/porelo-host/push/<project>.conf` from the sudo caller's home, and as root with `--check` by
`porelo-host-project remove` against Forgejo's `original_url`) together with `/etc/porelo-host/forge/central-ca.conf`
(`0644`, holding `forge_central_ca`). `porelo.host.bring` and `porelo.host.join` write each person's
`~/.config/porelo-host/push/<project>.conf` from the repositories they reach on the forge.
The helper gets the caller's local token from root's `porelo-host-person forge-token --for <login>`;
`--migrate` remains in the person's own account and gets it through `sudo -n porelo-host-person forge-token`.
APIs use `git.sock`; each local Git transfer uses a fresh root network namespace with a loopback-to-socket forwarder
and a credential pipe. No listener opens on the host's loopback. Central transfers retain HTTPS and their CA.
The checked sudoers drop-in admits `porelo-people`; the helper validates all arguments and current membership.

`/usr/local/sbin/porelo-host-project`, root's alone, registers an organization with an unlocked member in
`/etc/porelo-host/people/` (recording `member=<project> project-admin`) whom the applied registry in
`/etc/porelo-host/registry/applied.json` names as the project's admin, a signing key in Porelo's canonical
`ssh-ed25519 <base64>` signer format and a package-only publisher, or checks its commits against the central forge
before removing the project (including any `commit=`, `access_commit=` and `signer=` lines recorded by
`porelo-host-person sync`), dropping its memberships from `/etc/porelo-host/people/` and locking each person left with
none through `/usr/local/sbin/porelo-host-person lock`. Its credentials stay in memory and Forgejo;
[project registration](../../doc/local-forge.md#registering-a-project)
describes the records, refusal checks and failure behavior. Down removes the helper and project records.

The [resource bounds](../../doc/index.md) are set by `forge_cpus`, `forge_memory`, `forge_pids_limit`,
`forge_runner_cpus`, `forge_runner_memory` and `forge_runner_pids_limit`; job bounds use `forge_job_cpus`,
`forge_job_memory`, `forge_job_pids_limit` and `forge_job_omp_num_threads`. Their defaults and types are in
[`defaults/main.yml`](defaults/main.yml) and [`meta/argument_specs.yml`](meta/argument_specs.yml).

The runner takes `forge_runner_capacity` jobs at once, 2 by default, which fit the 16 processors of the server Porelo
rents. Before its configuration is written, the role
checks one budget with the VM pool: capacity × `forge_job_cpus` stays within half the host's processors, and capacity
× `forge_job_memory` plus the pool's VMs within half its `MemTotal`, so Forgejo, the runner and Porelo's own tasks keep
the other half. A refusal names both sides; the `capacity` entry point runs this check alone. A job's `actions/cache`
reaches the runner's cache on `127.0.0.1`, its server on `forge_runner_cache_port` (4000) and its proxy on
`forge_runner_cache_proxy_port` (4001), inside the shared container network namespace. No cache port is published.

The third gate socket, `/run/porelo-forge/runner.sock`, uses the same token-only gate as `git.sock`: no identity
header, cookies removed, and `401 Basic` without credentials, except the runner's own protocol under `/api/actions/`,
which Forgejo authenticates by the registration and runner tokens it carries. Its system socket unit uses the runner account's
primary group and mode `0660` in the existing `0755` directory. The runner account's
`forgejo-runner-proxy.container` mounts only this socket and runs two socat listeners on loopback at the web and Git
ports. Its image is pinned by digest. The proxy owns the network namespace; the runner depends on its service and
joins `container:forgejo-runner-proxy`, as do registration and every job. Registration uses
`http://127.0.0.1:<forge_http_port>`; existing registrations keep their token and move to that address.

Jobs inherit the proxy's `/etc/hosts`, where `AddHost=` maps `<host>.localhost` to `127.0.0.1`, so Forgejo's canonical
URL, checkout and package registry reach the token gate on loopback. Jobs receive no gate socket or forge CA trust
mounts. External HTTPS uses each image's own certificate authorities.

Forgejo's `ROOT_URL` is `http://<host>.localhost:<forge_http_port>/`, with browser port `3000` by default.
`forge_git_port` defaults to `3001`. These are the person's local forwarded ports, not listeners on the host.
Porelo forwards them over SSH to the two sockets and sets Git remotes to the Git port because Forgejo renders clone
URLs from its browser URL alone. See the [gate access contract](../../doc/local-forge.md#socket-gates).

A build publishes into the registry with the organization's Actions secret `PORELO_PUBLISHER_TOKEN`, a `write:package`
token of the account `porelo-publisher`, whose team may write the organization's packages and nothing else; a run's
own token is refused there. The token is made inside Forgejo's container and never read out, so it stays with the
forge and the runner's jobs and reaches no task.

`porelo_host_forge_agents` supplies `forge_agents`, a list of unique lower case names matching
`^[a-z][a-z0-9-]{0,30}$`, default `[]`. With repositories configured, each gets a Forgejo account `agent-<name>`
and membership in the owner's `agents` team: write access to code, pulls and issues on all its repositories,
read access to actions and packages, and no repository creation. Each token has scopes
`write:repository,read:package,read:organization` and stays in `/etc/porelo-host/forge/agents/<name>.token`,
root:root `0600`, in a root:root `0700` directory. Up keeps an existing token file and makes a missing one;
removing a name from the inventory leaves its account and token alone. Down removes the token directory with
the forge's settings and volumes.

`forge_variables` defaults to `PORELO_PUBLISH: "false"`, `JF_URL: "https://jfrog.invalid"`, `PORELO_DEPLOY_PROFILE:
forge-release` and `MAVEN_SNAPSHOTS_URL`, the forge's own Maven registry; GitHub holds the same names with its values.
`forge_placeholder_secrets` defaults to `[JF_ACCESS_TOKEN]`; missing secrets get `porelo-host-placeholder`,
and existing values are kept. Workflows differ between the forges only by variables and secrets.
