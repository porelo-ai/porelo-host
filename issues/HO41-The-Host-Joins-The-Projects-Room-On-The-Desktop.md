# HO41 — The Host Joins The Project's Room On The Desktop

**Status:** Idea.

**What must be true.** During the move a rented host's tasks talk in the project's room on the person's desktop,
reached through the VPN under the name the signed project file gives the homeserver, with the host's registration token
reaching the host on the stop's standard input alone.

## To be checked

- **The name:** porelo-project's signed `project.yml` names `homeserver: https://matrix.porelo.internal:<port>`, `room`
  and the CA's PEM text as `ca_certificate` for the move, and goes back to `{}` after the last one. The host resolves
  the name to the desktop's end of the VPN through a marked line `10.73.0.2 matrix.porelo.internal` in `/etc/hosts`,
  written by `up` and removed by `down`, as `roles/forge` does for `forge.porelo.internal`; tasks never see it, since
  the account's containers do not take the host's `/etc/hosts`.
- **The token:** one more need of [HO37](README.md#ho37)'s `--stdin`, `matrix-token <base64>`, written into
  `~/.config/porelo/matrix/host-registration-token` of Porelo's account, the account's own with mode `0600` in a
  `0700` directory, which the signed file names as `registration_token_file` (the transport expands `~/` against the
  account's home). It is the host's alone, made by the desktop's `admit`, and `down` removes it, since `vault clear`
  does not reach it.
- **When it is asked for:** the project is known only in `up`'s second play, once it is followed, so the need is not
  one of the stop's. Where the followed project names `registration_token_file` and the file is missing, `up` refuses
  with a message beginning `matrix-token:`, as it does for `forge-central-token`; the desktop then makes its own
  `porelo-host-stop --stdin matrix-token` call and runs `up` again. The stop takes the account from
  `/etc/porelo-host/stop.conf`, as for the vault. A project that names no `registration_token_file` is never asked.
- **The host's own homeserver** (`porelo-matrix-homeserver`, installed by [HO11](README.md#ho11)) is not the room
  during the move; its own token file is `~/.config/porelo/matrix/registration-token`, which this one never touches.
- **Agreed with porelo-message-matrix:** the path's form, the `~/` expansion, and `ca_certificate` in place of a
  committed `ca_file`; with porelo, that porelo passes the signed map on unchanged, so it needs no change of its own.
