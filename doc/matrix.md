# Matrix access

The host's shared homeserver runs as `porelo-matrix`. The Matrix transport package supplies the gate program;
the collection installs its system socket and service units. `/run/porelo-matrix/client.sock` is owned by
`porelo-matrix:porelo-people`, mode `0660`, in a `0755` directory. Every accepted connection starts
`/usr/bin/porelo-message-transport-matrix gate` as `porelo-matrix`, with the connected socket on standard input.
The gate authenticates the connecting login through Unix peer credentials.

Task containers must never receive `client.sock` or its containing directory. A container's connection would be
identified as its person's connection. The collection adds no mount for this socket.

The homeserver's listener is `$XDG_RUNTIME_DIR/porelo-matrix-gate/homeserver.sock`, mode `0600`, in a `0700`
directory owned by `porelo-matrix`. The role writes `PORELO_MATRIX_GATE=1` into its private `homeserver.conf`, in
which the transport's unit starts Tuwunel there, with nothing behind its loopback port, removes TCP and TLS settings, and runs
`gate --prepare` after package installation and before starting the homeserver. Successful preparation is recorded in a private `gate.prepared` file. The user unit's
runtime-directory setting recreates the private directory at boot. Gate services receive the service account's
`XDG_RUNTIME_DIR` explicitly.

`porelo-host-person sync <project>` takes the required `admins` list of logins from `porelo project verify --json`
after verification of the project's access bundle. Invalid or duplicate logins are refused before access changes.
It writes `/etc/porelo-host/matrix/<project>.admins`, one login per line, using a temporary file beside the target,
flush, fsync and rename. The directory is root:porelo-matrix `0750`; files are root:porelo-matrix `0640`. An unchanged
sync repairs a missing file without replaying developer admission. `porelo-host-project remove <project>` deletes
only that project's admins file. Links and paths writable by other accounts are refused.

Admission issues no Matrix machine or registration credential. Lock and purge run
`/usr/bin/porelo-message-transport-matrix expel <login>` as `porelo-matrix`; purge repeats expulsion after an earlier
lock. A transport failure stops removal without repeating captured output. The transport owns deactivation of the
person's `@<login>` and task `@*.<login>` accounts.

The socket unit, preparation ordering and authorization publication have unit checks. Live validation requires the
transport package providing `gate`, `gate --prepare` and login-based `expel`, and a homeserver package consuming the
Unix socket settings. The VM checks must establish that a nonmember gets `EACCES`, the homeserver has no TCP
listener, and purge deactivates the person's and tasks' accounts.
