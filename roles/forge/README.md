# Role `forge`

The host's forge: Forgejo with its package registry in rootless podman, as a quadlet user unit of an account of its
own (`porelo-forge`), serving HTTPS with a certificate from a CA made on the host. It runs
where the host setting `porelo_host_forge` is true, in `up`'s second play after the VPN; `down` stops it and keeps
nothing. Its runner gets an account of its own (`porelo-runner`), never Porelo's: what holds the forge's admin and the
person's token for the central forge shares no user namespace with a task.

The CA's certificate is `/etc/porelo-host/forge/ca.pem`; its key stays on the host, root's alone.

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

A build publishes into the registry with the organization's Actions secret `PORELO_PUBLISHER_TOKEN`, a `write:package`
token of the account `porelo-publisher`, whose team may write the organization's packages and nothing else; a run's
own token is refused there. The token is made inside Forgejo's container and never read out, so it stays with the
forge and the runner's jobs and reaches no task.

`forge_variables` defaults to `PORELO_PUBLISH: "false"`, `JF_URL: "https://jfrog.invalid"`, `PORELO_DEPLOY_PROFILE:
forge-release` and `MAVEN_SNAPSHOTS_URL`, the forge's own Maven registry; GitHub holds the same names with its values.
`forge_placeholder_secrets` defaults to `[JF_ACCESS_TOKEN]`; missing secrets get `porelo-host-placeholder`,
and existing values are kept. Workflows differ between the forges only by variables and secrets.
