# Matrix access

The host's shared homeserver runs as `porelo-matrix`. The Matrix transport package supplies the gate program;
the collection installs its system socket and service units. `/run/porelo-matrix/client.sock` is owned by
`porelo-matrix:porelo-people`, mode `0660`, in a `0755` directory. Every accepted connection starts
`/usr/libexec/porelo/transports/porelo-message-transport-matrix gate` as `porelo-matrix`, with the connected socket on standard input.
The gate authenticates the connecting login through Unix peer credentials.

Task containers must never receive `client.sock` or its containing directory. A container's connection would be
identified as its person's connection. The collection adds no mount for this socket.

The homeserver's listener is `$XDG_RUNTIME_DIR/porelo-matrix-gate/homeserver.sock`, mode `0600`, in a `0700`
directory owned by `porelo-matrix`. The role writes `PORELO_MATRIX_GATE=1` into its private `homeserver.conf`, in
which the transport's unit starts Tuwunel there, with nothing behind its loopback port, and makes the directory at each
start. It removes the TLS settings and runs `gate --prepare` after package installation and before starting the
homeserver, and once more after it answers, until `gate --prepare` reports `"administrator": true` and the gate holds
its admin token; only then is the preparation recorded in a private `gate.prepared` file. Gate services receive the
service account's `XDG_RUNTIME_DIR` explicitly and start after its user manager.

Each follow runs `keep-room --project <project> --persons <logins>` as `porelo-matrix` with the unlocked members.
It publishes the answered room in the project's member-readable file. When a project leaves, `keep-room` first
removes its members; after forge removal succeeds, `drop-room --project <project>` drops the room. No admins file
is written. Exit 75 is retried at the next follow; exit 78 leaves the room alone and is named in status.

Admission issues no Matrix machine or registration credential. Purge runs
`/usr/libexec/porelo/transports/porelo-message-transport-matrix expel <login>` as `porelo-matrix`, including after an earlier
lock. Expel takes the homeserver administrator's token on its stdin alone, as
`{"secrets":{"PORELO_MATRIX_ADMIN_TOKEN":"<token>"}}`; the helper reads it as `porelo-matrix` from the gate's
`gate/admin-token` and refuses a missing, empty or multi-word token before expel starts. A transport failure stops removal without repeating captured output. The transport owns deactivation of the
person's `@<login>` and task `@*.<login>` accounts.

The socket unit, preparation ordering and authorization publication have unit checks. Live validation requires the
transport package providing `gate`, `gate --prepare` and login-based `expel`, and a homeserver package consuming the
Unix socket settings. The VM checks must establish that a nonmember gets `EACCES`, the homeserver has no TCP
listener, and purge deactivates the person's and tasks' accounts.
