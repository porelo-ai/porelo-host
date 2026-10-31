# HO73 — The Homeserver Reached Through Its Gate

**Status:** Review.
**Size:** M - the matrix role's socket unit, Tuwunel's socket setting, the admins files written by the sync, and the TLS
and tokens removed with their Molecule steps; measured M median 63 min, from three M builds (47, 63, 75); grew from S,
as the TLS removal and the admins files came in.
**Blocked by:** porelo-message-matrix's gate.

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** The host's homeserver is reached only through the Matrix transport's gate on
`/run/porelo-matrix/client.sock`, which porelo-message-matrix brings, and by no other way from the host.

- A system socket unit, `SocketUser` porelo-matrix, `SocketGroup=porelo-people`, `SocketMode=0660`, `Accept=yes`, in
  `/run/porelo-matrix/` (0755), starts the gate as porelo-matrix; `gate --prepare` runs once after the homeserver unit
  is installed.
- Tuwunel listens on a Unix socket (`unix_socket_path`, 0600) in a 0700 directory of porelo-matrix's own, which only the
  gate reaches; never on TCP.
- No task's container gets `client.sock`, since `SO_PEERCRED` would take it for the person.
- The sync writes `/etc/porelo-host/matrix/<project>.admins` (directory root:porelo-matrix 0750, file 0640, one login
  per line), from the project's verified access file, atomically, and removes it with the project.
- A purge runs the transport's expel for the login, so its person and task accounts are deactivated with it.
- Goes: the homeserver's TLS, the machine and registration tokens on the host, the `matrix-token` stop.

## Acceptance

- a login outside `porelo-people` gets `EACCES` on client.sock; nothing of the homeserver listens on TCP; a purge
  deactivates `@<login>` and `@*.<login>`.

## Plan

- `roles/matrix/templates/porelo-matrix-gate.socket.j2` and `porelo-matrix-gate@.service.j2` as Matrix gave them
  (`ListenStream=/run/porelo-matrix/client.sock`, `Accept=yes`, `SocketUser`/`User` porelo-matrix,
  `SocketGroup=porelo-people`, `SocketMode=0660`, `ExecStart=/usr/libexec/porelo/transports/porelo-message-transport-matrix gate`,
  `StandardInput=socket`, `NoNewPrivileges=yes`), written by `roles/matrix/tasks/main.yml`.
- Tuwunel's settings (the `Add the homeserver's port…` task): `unix_socket_path` under `$XDG_RUNTIME_DIR/porelo-matrix/`
  (0700), `unix_socket_perms = 600`, no `port`/`address`; then `porelo-message-transport-matrix gate --prepare` once as
  porelo-matrix before the homeserver starts.
- Goes: the certificate tasks (line 128 on), the `matrix-token` need and stop, `publish --address` (line 207).
- `porelo-host-person sync` writes `/etc/porelo-host/matrix/<project>.admins` from the verified access file (one login
  per line, write, fsync, rename), `remove` deletes it; `purge` runs `porelo-message-transport-matrix expel <login>` as
  porelo-matrix.
- Red first: `test_porelo_host_person.py` for the admins file (content, modes, removal) and the expel call at purge.

## To be checked

- Tuwunel 1.9.4's `unix_socket_path` on a real run (Matrix read it in the binary only).
- The transport package's version that brings `gate` and `gate --prepare`.
