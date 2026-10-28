# HO41 — The Host Joins The Project's Room On The Laptop

**Status:** Estimated.
**Size:** M - one need of the stop with its unit tests, the hosts line in the VPN role, a refusal in `up`'s second
play, what `down` removes, the Molecule scenario's part, and the line contract; it waits on one field in porelo's
inventory.

**What must be true.** During the move a rented host's tasks talk in the project's room on the person's laptop,
reached through the VPN under the name the signed project file gives the homeserver, with the host's registration token
reaching the host on the stop's standard input alone.

## Plan

Read in the code (`9f883ec`), nothing measured.

- **The name: a marked line in the host's `/etc/hosts`** `<laptop's VPN address> matrix.porelo.internal`, written by
  the VPN role in `up`'s second play and removed by its `down`, as `roles/forge` does for `forge.porelo.internal`. The
  address is the person's peer's own, `porelo_host_vpn_peer_address` without its prefix, never a fixed `10.73.0.2`.
  Tasks never see it, since the account's containers do not take the host's `/etc/hosts`. The line belongs to the host,
  not to a project: it names the laptop, the same for every project the person puts on the host.
- **The token: one more need of [HO37](README.md#ho37)'s `--stdin`,** `matrix-token <base64>`. The stop writes it as
  Porelo's account (the account from `/etc/porelo-host/stop.conf`), into
  `~/.config/porelo/matrix/host-registration-token`: the directory made `0700` where missing, the file written beside
  its name with `umask 077` and moved over it, never through a link. It is checked like every other line before any
  is used: one line of base64, a token of the form `admit` gives, no newline inside.
- **When it is asked for:** the project is known only in `up`'s second play, so the need is not one of the stop's.
  Where the project names a `registration_token_file` and the file is missing or empty, `up` refuses with a message
  beginning `matrix-token:` (as with `forge-central-token:`). The laptop then runs
  `sudo -n porelo-host-stop --stdin matrix-token` and `up` again. A project that names no `registration_token_file` is
  never asked. A project naming another path than `~/.config/porelo/matrix/host-registration-token` is refused, naming
  the path, since the stop writes only that one.
- **How the play knows:** `porelo project inventory` lists `porelo_transports` with `scheme` and `package` only. The
  play needs the matrix transport's `registration_token_file` from the signed settings, which is a path and no secret.
  Agreed with porelo: a map `files` of the transport's `_file` settings in its entry. It is additive, so the
  inventory stays version 2 ("a play ignores what it does not read"). Until it is there, this is not buildable.
- **`down`** removes the token file and the hosts line. `vault clear` does not reach the file.
- **The host's own homeserver** (`porelo-matrix-homeserver`, [HO11](README.md#ho11)) is not the room during the move.
  Its own token file `~/.config/porelo/matrix/registration-token` is never touched.
- **In [PJ78](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj78)'s split:**
  - **The host's setup:** the hosts line and the token file. The token is the same for every project of that laptop:
    porelo-message-matrix's `admit` gives one per machine, not per project. It stays when a project is taken off and
    goes with the host's `down`.
  - **Putting a project on the host:** the question whether it is needed, since only the project's `project.yml` says
    so. The first project that names the file asks for it, a later one finds it there.
  - Today, before that split is built, both sit in `up` as described above.
- **Agreed with porelo-message-matrix:** the path's form, the `~/` expansion, and `ca_certificate` in place of a
  committed `ca_file`. With porelo, it passes the signed map on unchanged.

## Acceptance

- Molecule, each check seen red first:
  - a project naming the file and no token given: `up` stops with `matrix-token:`;
  - after `--stdin matrix-token`: the file is the account's, `0600` in a `0700` directory, equal to the given token;
  - a project naming another path is refused, naming it;
  - the hosts line names the peer's address, and the token appears in no other file, the journal or `up`'s output;
  - after `down`: the file and the line are gone.
- `test_porelo_host_stop.py`: `matrix-token` with a bad line, with a newline inside, and given twice is refused with 64
  before anything is written.

## To be checked

- porelo adds to each `porelo_transports` entry a map `files` of the transport's `_file` settings, paths only, the
  inventory staying version 2 (agreed by porelo's agent, 2026-10-28, an S of its own, after the split's plan); the play
  reads `files.registration_token_file`.
- That porelo-message-matrix's `admit` token has a fixed form the stop can check, or the stop checks only one line of
  printable ASCII.

## What [PJ78](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj78) changes

Recorded 2026-10-28. This stays the move's only, with the operator's laptop homeserver; it is not the split's model.
Under the split's (b) the project's Matrix settings live in its private `access.yml`, so the play reads
`registration_token_file` from the inventory's `files`, which porelo takes from the applied access file. Size unchanged.
