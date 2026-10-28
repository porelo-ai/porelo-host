# Role `forge`

The host's forge: Forgejo with its package registry in rootless podman, as a quadlet user unit of an account of its
own (`porelo-forge`), serving HTTPS with a certificate the person's own CA signed on their desktop. It runs
where the host setting `porelo_host_forge` is true, in `up`'s second play after the VPN; `down` stops it and keeps
nothing. Its runner gets an account of its own (`porelo-runner`), never Porelo's: what holds the forge's admin and the
person's token for the central forge shares no user namespace with a task.

The CA is the person's lasting one, made on their desktop; its certificate is `/etc/porelo-host/forge/ca.pem`, written
by the stop, and its key never reaches the host. `tasks_from: request`, in `up`'s first play, makes the forge's key and
a certificate request in `/etc/porelo-host/forge/` where no certificate signed by that CA holds for 30 days more and
names the forge's address and name, and adds `forge-certificate` to `porelo_host_needs`; `tls` moves the signed
certificate and its key into the forge account's `tls/`, never copying them, and refuses naming `forge-certificate`
where none holds. `/etc/porelo-host/forge.conf` names the forge's address, name, port, person and account to the stop
and the password script; it holds no secret.

With every forge, repositories or none, `forge_person` (default `operator`, matching `^[a-z][a-z0-9-]{0,30}$`) is the
person's web login, made only when absent, its generated password discarded; with repositories configured, it is also
in the organization's `Owners` team.
`/usr/local/sbin/porelo-host-forge-password`, root's alone, takes the person's lasting password on standard input and
sets it through the admin API with a token it makes for the call and keeps in memory; see the
[local forge guide](../../doc/local-forge.md#credentials-belong-to-their-destination). Down removes the script and
`forge.conf`.

`forge_porelo_account` defaults to `porelo_host_account` and matches `^[a-z][a-z0-9-]{0,30}$`. With repositories
configured, `porelo-<account>` belongs to `gates`, with code and pull request write access and Actions read access on
all of the organization's repositories. Its token (`write:repository,read:organization`) goes from Forgejo through a
pipe straight into that account's vault as `git.token.forge.porelo.internal`, only while the entry is missing.
No token file is made. Each configured repository's `main` refuses direct pushes and requires one approval; only
`forge_person` may approve and merge, with administrator merge overrides disabled and no required status checks.
Each such repository merges a pull request by fast-forward only, every other style off, so a pull request's own
commits reach `main` unchanged, with their author, signature and message, and the forge adds no commit of its own.
Up reads the settings back and keeps a matching rule unchanged.

Each repository is migrated once from the central forge, with its content, as an ordinary repository with no push
mirror. Only while a repository is still to migrate, the person's central token is needed: `up` refuses naming
`forge-central-token` until `porelo-host-stop --stdin forge-central-token`, run as root, has written it into
`/run/porelo-host/forge-central.token`, root's alone on the tmpfs, from where the shell reads it into the migration
request on a pipe. The migration removes it in an `always`, also when nothing was left to migrate; an `up` that fails
before the migration leaves it, root's alone, until the next `up` takes it, `down` or a reboot. The gathered push runs
elsewhere as a plain `git push` without force and refuses when central main moved; Forgejo's push mirrors force-push
and can erase central commits.
Previously configured push mirrors remain until `down` removes the forge's volumes; the next `up` migrates anew.

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

The forge's URLs use `https://forge.porelo.internal/` (`forge_name`) with no port. A root-owned system socket
forwards port 443 on loopback and the VPN's address to Forgejo's original HTTPS port (`forge_http_port`, 3000 by
default), which stays reachable on the VPN for the runner and existing clients. The role replaces
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
