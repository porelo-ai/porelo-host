# Role `forge`

The host's forge: Forgejo with its package registry in rootless podman, as a quadlet user unit of an account of its
own (`porelo-forge`), serving HTTPS with a certificate from a CA made on the host. It runs
where the host setting `porelo_host_forge` is true, in `up`'s second play after the VPN; `down` stops it and keeps
nothing. Its runner gets an account of its own (`porelo-runner`), never Porelo's: what holds the forge's admin and the
person's token for the central forge shares no user namespace with a task.

The CA's certificate is `/etc/porelo-host/forge/ca.pem`; its key stays on the host, root's alone.

With repositories configured, `forge_person` (default `operator`, matching `^[a-z][a-z0-9-]{0,30}$`) is the person's
web login in the organization's `Owners` team. Forgejo creates it only when absent, with a random first password
piped straight into `/etc/porelo-host/forge/person.password`, root:root `0600`, and requires a password change at the
first sign-in. Up keeps an existing account and password; it does not recreate a first password file the person
deleted. Fetch the file over SSH into a private file, then delete both copies after signing in as described in the
[local forge guide](../../doc/local-forge.md#credentials-belong-to-their-destination). Down removes the password file
with the forge's CA directory.

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
mirror. The person's central token is read from `forge_central_token_path` by the shell into the migration request
on a pipe. The gathered push runs elsewhere as a plain `git push` without force and refuses when central main moved;
Forgejo's push mirrors force-push and can erase central commits.
Previously configured push mirrors remain until `down` removes the forge's volumes; the next `up` migrates anew.

The [resource bounds](../../doc/index.md) are set by `forge_cpus`, `forge_memory`, `forge_pids_limit`,
`forge_runner_cpus`, `forge_runner_memory` and `forge_runner_pids_limit`; job bounds use `forge_job_cpus`,
`forge_job_memory`, `forge_job_pids_limit` and `forge_job_omp_num_threads`. Their defaults and types are in
[`defaults/main.yml`](defaults/main.yml) and [`meta/argument_specs.yml`](meta/argument_specs.yml).

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
