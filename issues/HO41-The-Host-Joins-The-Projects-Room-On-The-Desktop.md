# HO41 — The Host Joins The Project's Room On The Desktop

**Status:** Idea; blocked by porelo [B304](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b304).

**What must be true.** A rented host's tasks talk in the project's room on the person's desktop, reached through the
VPN, with the admission's values set through Porelo's own command and the registration token reaching the host's vault
on the stop's standard input alone.

## To be checked

- **The call, as porelo [B304](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b304) proposes it:** the stop runs, as the account,
  `porelo talk settings <project> matrix --set homeserver=<url> --set room=<id> --ca <file>
  --registration-token-from-stdin`, the token on that command's standard input. The CA is no secret: the stop writes it
  for the call into a file the account reads and removes it after.
- **The stop's lines:** a need `matrix` with the lines `matrix-homeserver`, `matrix-room`, `matrix-ca` and
  `matrix-token`, each in [HO37](README.md#ho37)'s form, every one checked before any is used; porelo-frontend's
  pipeline sends them from the admission the interface took into `secrets.kdbx`.
- **When it is asked for:** the project is known only in `up`'s second play, once it is followed, so the need is not
  one of the stop's. Where the followed project names a remote room and `porelo talk settings` reports no admission
  for it, `up` refuses with a message beginning `matrix:`, as it does for `forge-central-token`; the desktop then makes
  its own `porelo-host-stop --stdin matrix` call and runs `up` again. The stop takes the project's name from
  `/etc/porelo-host/stop.conf`, which `roles/porelo/tasks/project.yml` then writes beside the account's. A host whose
  project names no remote room is never asked.
- **The host's own homeserver** (`porelo-matrix-homeserver`, installed by [HO11](README.md#ho11)) is not the room
  during the move, and stays installed, enabled by nothing.
