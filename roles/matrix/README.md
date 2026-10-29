# Role `matrix`

The host's shared Matrix homeserver: `porelo-matrix-homeserver` and `porelo-message-transport-matrix` installed from
Porelo's apt repository and run under an account of its own (`porelo-matrix`) with linger, subordinate UID and GID
ranges, and delegated cgroup controllers checked by `porelo.host.base`'s `controllers` entry point. Nothing of a person
or project reaches this role.

The host resolves `matrix_name` (`matrix.<porelo_host_name>.porelo.internal` by default) to `127.0.0.1` through a marked
`/etc/hosts` block. `~/.config/porelo/matrix/homeserver.conf`, owned by `matrix_account` with mode `0600` inside `0700`
directories, receives `PORELO_MATRIX_PORT` (`8448` by default) and `PORELO_MATRIX_SERVER_NAME` (`matrix_name`) only
where absent, leaving lines written by the transport untouched.

`porelo.host.forge`'s `request` entry point in `up`'s first play requests the homeserver's certificate beside the
forge's under the single `forge-certificate` stop need. This role moves `/etc/porelo-host/forge/matrix.pem` and
`matrix.key` into `~/.config/porelo/matrix/tls/server.crt` (`0600`) and `tls/server.key` (`0600`, inside `0700` `tls/`),
places `/etc/porelo-host/forge/ca.pem` at `~/.config/porelo/matrix/ca.crt` (`0644`), all written by `matrix_account`
itself, and refuses naming `forge-certificate` where no valid certificate holds.

The role enables and starts the user unit `porelo-matrix-homeserver.service` and runs
`matrix_transport_command publish --address <matrix_address>:<matrix_port> --name <matrix_name>` as `matrix_account`
whenever `PORELO_MATRIX_PUBLISH` in `homeserver.conf` differs. `tasks_from: down` removes the marked `/etc/hosts` block,
and where `matrix_account` exists, stops and disables `porelo-matrix-homeserver.service`, runs `publish --off`, removes
any containers and the database volume, disables linger, stops the account's user manager, and deletes the account with
its home directory.

## Requirements

Ubuntu 26.04, run as root on the host itself (`-c local`), after Porelo's apt repository is configured and the stop has
provided `forge-certificate`.

## Variables

| Variable | Default | What it is |
|---|---|---|
| `matrix_account` | `porelo-matrix` | The account the host's Matrix homeserver runs as. |
| `matrix_address` | `10.73.{{ porelo_host_network }}.1` | The host's VPN address where the homeserver is published. |
| `matrix_name` | `matrix.{{ porelo_host_name }}.porelo.internal` | The homeserver's DNS name on `/etc/hosts` and its TLS certificate. |
| `matrix_port` | `8448` | The TCP port the homeserver listens on locally and publishes on the VPN. |
| `matrix_transport_command` | `/usr/libexec/porelo/transports/porelo-message-transport-matrix` | The Matrix transport binary from `porelo-message-transport-matrix`. |

## License

GPL-3.0-or-later.
