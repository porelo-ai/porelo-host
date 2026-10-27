# HO07 — The Project's Store Restored And Kept

**Status:** Backlog; blocked by [HO37](README.md#ho37), by porelo-project [PJ45](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj45), and by
porelo-message-matrix [MX24](https://github.com/porelo-ai/porelo-message-matrix/blob/main/issues/README.md#mx24), and by
porelo [B231](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b231), and by porelo-message-matrix
[MX39](https://github.com/porelo-ai/porelo-message-matrix/blob/main/issues/README.md#mx39)
(a late completion or a second backup into the same directory loses messages).
**Size:** L - one role, a script and a timer here, but every entry's copy and restore is another repository's command,
and the round trip is measured on a rented host.

**What must be true.** At `up`, the data the project keeps comes back from its store before anything that reads it
starts; while the host runs, a timer copies it every hour; at `down`, a last copy is made before anything stops. Each
entry is copied and restored by the command its owner gives, and the store's keys reach restic from the person's
secrets file on the stop's standard input, never through Ansible.

## Plan

- **Decided: Scaleway Object Storage**, a bucket of the project's, with a key that may write and delete in that
  bucket only; a second bucket with Object Lock comes with the event log, later.
- **One role, `store`**: `needs.yml` (in `up`'s first play, naming `store` in `porelo_host_needs` while a file of
  `/etc/porelo-host/store/` is missing), `install.yml` (restic, its release pinned by version and its SHA-256 from
  restic's own `SHA256SUMS`, checked before use), `keep.yml` (the script and the units), `restore.yml`, and
  `down.yml` (the last copy, then `/etc/porelo-host/store/` removed).
- **The list is data, its entries commands**: `store_entries` names each entry with its command that writes a
  consistent copy into a directory, the one that puts it back, its schedule (`hourly` or `down`) and how many restic
  keeps: the room (porelo-message-matrix's `backup|restore <dir>`, 48), the usage records (`porelo keep [--restore]
  <dir>`, 48; 0 done, 70 failed, and `--restore` alone 69 while a task runs), the Maven cache (copied as it stands at
  `down`, 1). The vault is never an entry.
- **One script, `porelo-host-keep`**, run as root, since only root reads the store's keys: for each entry due, its
  command, run as the account with `runuser`, into a fresh directory, `restic backup --tag <entry>` of it, `restic
  forget --tag <entry> --keep-last <n>`; it stops at the first entry that fails and exits non-zero naming it, so a half
  copy is never thinned against.
- **A systemd timer of root's**, hourly while the host runs; `down` runs the script once with `--all` before
  [HO09](README.md#ho09) stops anything, and stops `down` if it fails.
- **At `up`**, before the homeserver and the first `porelo task start`: `restic restore latest --tag <entry>` into a
  fresh directory and the entry's restore command, for each entry; a store with no snapshot yet is a first start and
  restores nothing, said so.
- **The room's commands, as porelo-message-matrix
  [MX24](https://github.com/porelo-ai/porelo-message-matrix/blob/main/issues/README.md#mx24) plans them**: `backup
  <dir>` into an existing empty directory, 0 with `{"backup": <id>}`, 75 when the homeserver is not active or no backup
  appeared within 60 s, which fails that run, 78 when the unit is not installed; `restore <dir>` before the
  homeserver's `setup`, 0 with `{"restore": <id>}`, or with `{"restore": "present"}` on a second `up` where the
  database already is, which counts as unchanged; 78 for anything really wrong.
- **The store's address and keys** (decided: `--stdin` lines of the person's stop, from `secrets.kdbx`, since the
  host has no drive and the vault hands no value out) are written by `porelo-host-stop --stdin` root-only into
  `/etc/porelo-host/store/` for the host's life, since the hourly copy and the last copy at `down` need them
  unattended, and `down` removes them. The need is `store`, its lines in [HO37](README.md#ho37)'s form `store <name>
  <value in base64>`, one each for `repository`, `password` and `s3-credentials`, each written to
  `/etc/porelo-host/store/<name>`, root's with mode `0600`, and refused where a name is not one of the three. They
  reach restic through its environment as `RESTIC_REPOSITORY_FILE`, `RESTIC_PASSWORD_FILE` and the S3 credentials
  file; the role checks they are there, never reads them. porelo-frontend's pipeline sends them once this is built.
  **An accepted risk**, written into `doc/decisions.md` with the change: the keys lie in the clear on the host's disk,
  as the VPN's key does, readable by its root and the provider's disk images; it stays because the hourly copy and the
  last copy at `down` run with nobody there, and it would change if restic could take its keys from a sealed store or
  the vault on a pipe at each run.
- **Touches, beyond the role:** `playbooks/up.yml` (its `needs` in the first play), `playbooks/down.yml`,
  `roles/porelo/files/porelo-host-stop` (the need `store`), `doc/lines.md`, `doc/decisions.md`, `doc/index.md`, and
  `AGENTS.md`'s list of files that cannot be Java (`porelo-host-keep`).
- **Red first**: a room with a message, the store copied, a fresh VM brought up from it, and the message read; the
  same without `restore.yml` finds the room empty.

## Acceptance

- The round trip of the red test, on the test VM `build/molecule.sh` makes against a test bucket, then once on a rented host
  with its time measured.
- A failing entry command stops the timer's run and `down`, names the entry, and no `forget` runs after it.
- `restic snapshots` shows each entry under its tag, at most its count kept.
