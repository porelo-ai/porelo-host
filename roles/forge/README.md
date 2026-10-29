# Role `forge`

The host's forge: Forgejo with its package registry in rootless podman, as a quadlet user unit of an account of its
own (`porelo-forge`), serving HTTPS with a certificate the person's own CA signed on their desktop. It runs
where the host setting `porelo_host_forge` is true, in `up`'s second play after the VPN; `down` stops it and keeps
nothing. Its runner gets an account of its own (`porelo-runner`), never Porelo's: what holds the forge's admin and the
person's token for the central forge shares no user namespace with a task.

The CA is the host's lasting one, made on the admin's desktop; its certificate is `/etc/porelo-host/forge/ca.pem`,
written by the stop, and its key never reaches the host. `tasks_from: request`, in `up`'s first play whether or not
`porelo_host_forge` is true, makes keys and certificate requests in `/etc/porelo-host/forge/` for both the forge
(`forge.key`, `forge.csr`) and the homeserver (`matrix.key`, `matrix.csr`) where either certificate signed by that CA
does not hold for 30 days more with the host's VPN address and its DNS name, and adds `forge-certificate` to
`porelo_host_needs`. `tls` moves the forge's signed certificate and its key into the forge account's `tls/`, never
copying them, and refuses naming `forge-certificate` where none holds. `/etc/porelo-host/forge.conf` names the host's
VPN address, host label, forge name, homeserver name, port, account and configured agents to the stop and the host's
helpers; it holds no secret.

`up` creates no default forge user, and deletes an unrecorded `operator` forge user left outside
`/etc/porelo-host/people/`. Each person gets their forge login when admitted by `porelo-host-person`.
`/usr/local/sbin/porelo-host-forge-password`, root's alone and run through `sudo` as an admitted person, takes their
lasting password on standard input and sets it on their own login through the admin API with a token it makes for the
call and keeps in memory; direct root calls without `SUDO_USER` refuse with `64`; see the
[local forge guide](../../doc/local-forge.md#credentials-belong-to-their-destination). Down removes the script and
`forge.conf`.

`up` prepares the forge without repositories (`forge_repositories` stays empty on the host); the repository migration,
gate, branch protection, publisher, agent token and gathered push task files remain on disk uncalled by `up`.

`/usr/local/sbin/porelo-host-project`, root's alone, registers an organization with an unlocked member in
`/etc/porelo-host/people/` (recording `member=<project> project-admin`), a signing key in Porelo's canonical
`ssh-ed25519 <base64>` signer format and a package-only publisher, or checks its commits against the central forge
before removing the project, dropping its memberships from `/etc/porelo-host/people/` and locking each person left with
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
reaches the runner's cache on the forge's address, its server on `forge_runner_cache_port` (4000) and its proxy on
`forge_runner_cache_proxy_port` (4001), both published there alone.

The forge's URLs use `https://forge.<porelo_host_name>.porelo.internal/` (`forge_name`) with no port. A root-owned
system socket forwards port 443 on loopback and the VPN's address to Forgejo's original HTTPS port (`forge_http_port`,
3000 by default), which stays reachable on the VPN for the runner and existing clients. The role replaces
`/etc/systemd/system/porelo-forge-https.socket` and `porelo-forge-https.service` from templates; `down` stops and
disables both and removes them before stopping Forgejo. The socket may bind before the VPN address exists at boot.
The host resolves `forge_name` to `127.0.0.1` through a marked `/etc/hosts` block; `down` removes only that block.

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
the forge's CA and volumes.

`forge_variables` defaults to `PORELO_PUBLISH: "false"`, `JF_URL: "https://jfrog.invalid"`, `PORELO_DEPLOY_PROFILE:
forge-release` and `MAVEN_SNAPSHOTS_URL`, the forge's own Maven registry; GitHub holds the same names with its values.
`forge_placeholder_secrets` defaults to `[JF_ACCESS_TOKEN]`; missing secrets get `porelo-host-placeholder`,
and existing values are kept. Workflows differ between the forges only by variables and secrets.
