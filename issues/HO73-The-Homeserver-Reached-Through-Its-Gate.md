# HO73 — The Homeserver Reached Through Its Gate

**Status:** Accepted (operator, 2026-10-30, with the project's one-click joining).
**Size:** S - the matrix role's system socket unit for the transport's gate, Tuwunel off TCP and the tokens out, with a
VM run; measured S 54 min, from one S build only, so nearly a guess.
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

## Tests

- a login outside `porelo-people` gets `EACCES` on client.sock; nothing of the homeserver listens on TCP; a purge
  deactivates `@<login>` and `@*.<login>`.
