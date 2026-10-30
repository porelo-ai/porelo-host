# HO69 — The Forge Behind Its Gate Without TLS

**Status:** Accepted (operator, 2026-10-30, with the project's one-click joining).
**Size:** M - the CA and TLS out, the gate's two sockets with unit tests, Forgejo's settings and a VM run; measured M
median 63 min, from three M builds (47, 63, 75).
**Blocked by:** [HO71](README.md#ho71).

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** The host's forge has no TLS and no password. A person's browser reaches it through the tunnel at
`http://<host>.localhost:<forge web port>/`, signed in as the person; Git and the API reach it only with a token.

- Forgejo itself listens on a Unix socket in a 0700 directory of the forge account (`PROTOCOL=http+unix`,
  `UNIX_SOCKET_PERMISSION=600`, mapped into the rootless container), so only the gate, in that account, reaches it; no
  TCP port.
- The gate serves two system socket units (`SocketUser` the forge account, `SocketGroup=porelo-people`,
  `SocketMode=0660`, in `/run/porelo-forge/`, 0755). On both it removes every `X-WEBAUTH-*` header a caller sends.
- `web.sock`: it maps the caller's uid from `SO_PEERCRED` to a login admitted in `porelo-people`, never root or a
  service account, and sets the reverse-proxy user header only on a request with no `Authorization` header. It refuses
  Forgejo's routes that set a password or make tokens (`/user/settings/account`, `/user/settings/applications` and their
  API twins), so a person can neither give themselves a password nor mint a token the host does not track.
- `git.sock`, for Git over HTTP and the API: it sets no user header, removes `Cookie`, answers a request without
  credentials with `401` and `WWW-Authenticate: Basic`, as Git expects before it asks its credential helper, and passes
  a request with a token on, Basic or `token`, to Forgejo.
- A task's container gets neither socket nor a token: the host's task gate passes the task's branch on to `git.sock`
  with the task's own token ([HO71](README.md#ho71)), so nothing that runs as the person's uid gets their forge rights.
  The person's own Git takes their token through Porelo's credential helper, and Porelo sets their remotes to the local
  `git_port`, since Forgejo renders clone URLs from `ROOT_URL` alone.
- Forgejo: `ENABLE_REVERSE_PROXY_AUTHENTICATION=true` for the web interface,
  `ENABLE_REVERSE_PROXY_AUTHENTICATION_API=false`, `ENABLE_REVERSE_PROXY_AUTO_REGISTRATION=false`; its SSH server off;
  `ROOT_URL` exactly `http://<host>.localhost:<forge web port>/`. The host card's services name `forge: {web_port,
  git_port}`, the local ports Porelo forwards to `web.sock` and `git.sock`.
- Goes: the forge's CA, its certificate and request, the `forge-certificate` stop, the HTTPS socket units, the CA's
  trust in the accounts, `porelo-host-forge-password`, the forge's SSH port.

## Tests

- a header sent from outside is dropped on both sockets; `web.sock` gives the caller's login and nothing to root or a
  service account;
- `web.sock` refuses the password and token routes; `git.sock` answers 401 Basic first, then acts as the token's owner,
  and never trusts a cookie or the header;
- `git clone` through `git.sock` with the credential helper works; Forgejo's own socket refuses every account but the
  forge's.
