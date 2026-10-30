# HO69 — The Forge Behind Its Gate Without TLS

**Status:** Accepted (operator, 2026-10-30, with the project's one-click joining).
**Size:** M - the CA and TLS out, the gate's two sockets with unit tests, Forgejo's settings and a VM run; measured M
median 63 min, from three M builds (47, 63, 75).
**Blocked by:** [HO71](README.md#ho71).

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** The host's forge has no TLS and no password. A person's browser reaches it through the tunnel at
`http://<host>.localhost:<forge web port>/`, signed in as the person; Git and the API reach it only with a token.

- Forgejo itself listens on a Unix socket of the forge account, 0600 (`PROTOCOL=http+unix`), so only the gate, in that
  account, reaches it; no TCP port.
- The gate serves two system socket units (`SocketUser` the forge account, `SocketGroup=porelo-people`,
  `SocketMode=0660`, in `/run/porelo-forge/`, 0755): `web.sock`, where it sets the reverse-proxy user header to the
  caller's login from `SO_PEERCRED` on a request with no `Authorization` header; and `git.sock`, for Git over HTTP and
  the API, where it sets no user header and passes only token requests. On both it removes every `X-WEBAUTH-*` header a
  caller sends.
- A task's container gets neither socket nor a token: the host's task gate passes the task's branch on to `git.sock`
  with the task's own token ([HO71](README.md#ho71)), as Porelo's reach rules say, so nothing that runs as the person's
  uid gets their forge rights. The person's own Git takes the token the sync writes for them, through Porelo's
  credential helper. The host card's services name `forge: {web_port, git_port}`, the local ports Porelo forwards to
  `web.sock` and `git.sock`.
- Forgejo: `ENABLE_REVERSE_PROXY_AUTHENTICATION=true` for the web interface,
  `ENABLE_REVERSE_PROXY_AUTHENTICATION_API=false`, `ENABLE_REVERSE_PROXY_AUTO_REGISTRATION=false`; its SSH server off.
- `ROOT_URL` is exactly `http://<host>.localhost:<forge web port>/`, the port from the host card's services, so the
  forge's links and its WebAuthn relying party are the same on every person's machine.
- Goes: the forge's CA, its certificate and request, the `forge-certificate` stop, the HTTPS socket units, the CA's
  trust in the accounts, `porelo-host-forge-password`, the forge's SSH port.

## Tests

- a header sent from outside is dropped on both sockets; `web.sock` gives the caller's login, and nothing without a
  matching uid;
- `git.sock` refuses a request without a token and acts as the token's owner; the API never trusts the header;
- Forgejo's own socket refuses every account but the forge's.
