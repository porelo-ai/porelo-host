# HO07 — The Project's Store Restored And Kept

**Status:** Backlog; blocked by porelo-project [PJ45](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj45), and by
porelo-message-matrix [MX24](https://github.com/porelo-ai/porelo-message-matrix/blob/main/issues/README.md#mx24), and by
porelo [B231](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b231).
**Size:** L - one role, a script and a timer here, but every entry's copy and restore is another repository's command,
and the round trip is measured on a rented host.

**What must be true.** At `up`, the data the project keeps comes back from its store before anything that reads it
starts; while the host runs, a timer copies it every hour; at `down`, a last copy is made before anything stops. Each
entry is copied and restored by the command its owner gives, and the store's keys reach restic from the person's
drive, never through Ansible.

## Plan

- **Decided: Scaleway Object Storage**, a bucket of the project's, with a key that may write and delete in that
  bucket only; a second bucket with Object Lock comes with the event log, later.
- **One role, `store`**: `install.yml` (restic, its release pinned by version and its SHA-256 from restic's own
  `SHA256SUMS`, checked before use), `keep.yml` (the script and the units), `restore.yml`.
- **The list is data, its entries commands**: `store_entries` names each entry with its command that writes a
  consistent copy into a directory, the one that puts it back, its schedule (`hourly` or `down`) and how many restic
  keeps: the room (porelo-message-matrix's `backup|restore <dir>`, 48), the usage records (`porelo keep [--restore]
  <dir>`, 48; 0 done, 70 failed, and `--restore` alone 69 while a task runs), the Maven cache (copied as it stands at
  `down`, 1). The vault is never an entry.
- **One script, `porelo-host-keep`**, installed for the account: for each entry due, its command into a fresh
  directory, `restic backup --tag <entry>` of it, `restic forget --tag <entry> --keep-last <n>`; it stops at the
  first entry that fails and exits non-zero naming it, so a half copy is never thinned against.
- **A systemd user timer**, hourly while the host runs; `down` runs the script once with `--all` before
  [HO09](README.md#ho09) stops anything, and stops `down` if it fails.
- **At `up`**, before the homeserver and the first `porelo task start`: `restic restore latest --tag <entry>` into a
  fresh directory and the entry's restore command, for each entry; a store with no snapshot yet is a first start and
  restores nothing, said so.
- **The store's address and keys** (decided: the drive, since the vault hands no value out) reach restic through its
  environment, as files on the person's drive
  ([HO06](README.md#ho06)): `RESTIC_REPOSITORY_FILE`, `RESTIC_PASSWORD_FILE` and an S3 credentials file; the role
  checks they are there, never reads them.
- **Red first**: a room with a message, the store copied, a fresh VM brought up from it, and the message read; the
  same without `restore.yml` finds the room empty.

## Acceptance

- The round trip of the red test, on the test VM `build/molecule.sh` makes against a test bucket, then once on a rented host
  with its time measured.
- A failing entry command stops the timer's run and `down`, names the entry, and no `forget` runs after it.
- `restic snapshots` shows each entry under its tag, at most its count kept.

## To be checked

- The room's entry commands' names and exit codes, once porelo-message-matrix plans them.
