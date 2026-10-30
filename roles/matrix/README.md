# Role `matrix`

The host's shared Matrix homeserver: `porelo-matrix-homeserver` and `porelo-message-transport-matrix` installed from
Porelo's apt repository and run under an account of its own (`porelo-matrix`) with linger, subordinate UID and GID
ranges, and delegated cgroup controllers checked by `porelo.host.base`'s `controllers` entry point. Nothing of a person
or project reaches this role.

The system socket `/run/porelo-matrix/client.sock` belongs to `matrix_account:porelo-people`, mode `0660`, in a
`0755` directory. Each connection starts `/usr/bin/porelo-message-transport-matrix gate` as `matrix_account`, with
the connected socket on standard input and `NoNewPrivileges=yes`. The gate program belongs to the transport package.
Task containers must never receive this socket: its peer credentials would identify the person running the container.

`~/.config/porelo/matrix/homeserver.conf` is private (`0600` inside `0700` directories). The role sets
`PORELO_MATRIX_GATE=1`, in which the transport's unit starts Tuwunel on
`$XDG_RUNTIME_DIR/porelo-matrix-gate/homeserver.sock` (mode `600`), with nothing behind its loopback port, removes
the TLS settings, and keeps `PORELO_MATRIX_SERVER_NAME` equal to `matrix_name`. The transport's unit makes the
private `0700` socket directory at each start. After installing the homeserver package, the role runs
`matrix_transport_command gate --prepare` as `matrix_account` before starting the homeserver. A private
`gate.prepared` marker records successful preparation, so later runs do not repeat it.

The role removes its old TLS files and the old host admin token. It neither publishes a TCP address nor issues
machine tokens. Project sync writes the gate's authorization files as described in [Matrix access](../../doc/matrix.md).
`tasks_from: down` stops and removes the gate units and admins files, stops and disables the homeserver, removes
its containers and database volume, disables linger, stops its user manager, and deletes its account and home.

## Requirements

Ubuntu 26.04, run as root on the host itself (`-c local`), after Porelo's apt repository is configured. The installed
transport must provide `gate`, `gate --prepare` and `expel <login>`.

## Variables

| Variable | Default | What it is |
|---|---|---|
| `matrix_account` | `porelo-matrix` | The account the host's Matrix homeserver runs as. |
| `matrix_name` | `matrix.{{ porelo_host_name }}.porelo.internal` | The homeserver's server name. |
| `matrix_transport_command` | `/usr/bin/porelo-message-transport-matrix` | The transport command used for gate preparation. The socket unit uses the package's fixed `/usr/bin` path. |

## License

GPL-3.0-or-later.
