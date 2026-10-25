# Role `forge`

The host's forge: Forgejo with its package registry in rootless podman, as a quadlet user unit of an account of its
own (`porelo-forge`), serving HTTPS with a certificate from a CA made on the host. It runs
where the host setting `porelo_host_forge` is true, in `up`'s second play after the VPN; `down` stops it and keeps
nothing. Its runner gets an account of its own (`porelo-runner`), never Porelo's: what holds the forge's admin and the
person's token for the central forge shares no user namespace with a task.

The CA's certificate is `/etc/porelo-host/forge/ca.pem`; its key stays on the host, root's alone.

The forge's URLs use `https://forge.porelo.internal/` (`forge_name`) with no port. A root-owned system socket
forwards port 443 on loopback and the VPN's address to Forgejo's original HTTPS port (`forge_http_port`, 3000 by
default), which stays reachable on the VPN for the runner and existing clients. The role replaces
`/etc/systemd/system/porelo-forge-https.socket` and `porelo-forge-https.service` from templates; `down` stops and
disables both and removes them before stopping Forgejo. The socket may bind before the VPN address exists at boot.

A build publishes into the registry with the organization's Actions secret `PORELO_PUBLISHER_TOKEN`, a `write:package`
token of the account `porelo-publisher`, whose team may write the organization's packages and nothing else; a run's
own token is refused there. The token is made inside Forgejo's container and never read out, so it stays with the
forge and the runner's jobs and reaches no task.
