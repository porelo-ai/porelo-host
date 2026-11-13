# HO07 — The Project's Store Restored And Kept

```json
{
  "$schema": "issue-1.json",
  "id": "HO07",
  "title": "The Project's Store Restored And Kept",
  "state": "Backlog",
  "size": "L",
  "priority": "Medium",
  "rank": 1,
  "blockedBy": [],
  "covers": "Role `store`: restic pinned, each entry's own copy and restore command, an hourly timer of root's, a last copy at `down`, the restore before anything reads it."
}
```

**Why this size.** one role, a script and a timer here, but every entry's copy and restore is another repository's command,
and the round trip is measured on a rented host.

**2026-11-04:** It waits for the room's `backup <dir>` and `restore <dir>`,
for a backup that holds only its own copy and never empties a directory another one filled (a late completion or a
second backup into the same directory loses messages), and for `porelo keep [--restore] <dir>`.

**What must be true.** At `up`, the data the project keeps comes back from its store before anything that reads it
starts; while the host runs, a timer copies it every hour; at `down`, a last copy is made before anything stops. Each
entry is copied and restored by the command its owner gives, and the store's keys reach the host once, by a command a
host admin runs as root over SSH with their card, on its standard input, never through Ansible.

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
- **Each entry's account:** the room's is `porelo-matrix`; the usage records and the Maven cache are each person's own
  account, as every person runs their own Porelo, so those entries run once per person on the host. The cache is the project's shared
  dependency cache Porelo plans, in the data folder of the account that runs the task; until that is built there is no
  cache to copy, and a task's own Maven folder is no entry.
- **One script, `porelo-host-keep`**, run as root, since only root reads the store's keys: for each entry due, its
  command, run with `runuser` as the entry's account, into a fresh directory, `restic backup --tag <entry>` of it, `restic
  forget --tag <entry> --keep-last <n>`; it stops at the first entry that fails and exits non-zero naming it, so a half
  copy is never thinned against.
- **A systemd timer of root's**, hourly while the host runs; `down` runs the script once with `--all` before
  [HO09](README.md#ho09) stops anything, and stops `down` if it fails.
- **At `up`**, before the homeserver and the first `porelo task start`: `restic restore latest --tag <entry>` into a
  fresh directory and the entry's restore command, for each entry; a store with no snapshot yet is a first start and
  restores nothing, said so.
- **The room's commands**, porelo-message-matrix's: `backup
  <dir>` into an existing empty directory, 0 with `{"backup": <id>}`, 75 when the homeserver is not active or no backup
  appeared within 60 s, which fails that run, 78 when the unit is not installed; `restore <dir>` before the
  homeserver's `setup`, 0 with `{"restore": <id>}`, or with `{"restore": "present"}` on a second `up` where the
  database already is, which counts as unchanged; 78 for anything really wrong.
- **The store's address and keys** come from the person's password database by a new one-time command, which a host
  admin runs as root over SSH with their card, since the stop takes no secret as root any more and the vault hands no
  value out. It writes them root-only into `/etc/porelo-host/store/` for the host's life, since the hourly copy and the
  last copy at `down` need them unattended, and `down` removes them. Its lines on standard input are `store <name>
  <value in base64>`, one each for `repository`, `password` and `s3-credentials`, each written to
  `/etc/porelo-host/store/<name>`, root's with mode `0600`, and refused where a name is not one of the three. They
  reach restic through its environment as `RESTIC_REPOSITORY_FILE`, `RESTIC_PASSWORD_FILE` and the S3 credentials
  file; the role checks they are there, never reads them. **A deliberate exception**, in
  [`doc/decisions.md`](../doc/decisions.md#the-stores-keys-on-the-host): the keys lie in the clear on the host's disk,
  readable by its root and the provider's disk images; the key is limited to its bucket.
- **Touches, beyond the role:** `playbooks/up.yml` (its `needs` in the first play), `playbooks/down.yml`, the new
  command, `doc/lines.md`, `doc/index.md`, and `AGENTS.md`'s list of files that cannot be Java (`porelo-host-keep`).
- **Red first**: a room with a message, the store copied, a fresh VM brought up from it, and the message read; the
  same without `restore.yml` finds the room empty.

## Acceptance

- The round trip of the red test, on the test VM `build/molecule.sh` makes against a test bucket, then once on a rented host
  with its time measured.
- A failing entry command stops the timer's run and `down`, names the entry, and no `forget` runs after it.
- `restic snapshots` shows each entry under its tag, at most its count kept.

## The cut (2026-11-13)

Agreed with the coordinator (2026-11-12, 23:57Z). Under today's rule only four collection programs reach a host, and
host administration belongs to the pinned `porelo-host` package. So the plan's script `porelo-host-keep` and its
one-time key command move to porelo, as `porelo-host store put|keep|restore`. The issue text went to Agent Core in the
room to file in porelo (Backlog, Medium).

What stays here is the `store` role:
- restic, pinned by version and checked against restic's own `SHA256SUMS`;
- root's hourly timer that runs `porelo-host store keep`;
- `up` running `porelo-host store restore` before the homeserver;
- `down` running `porelo-host store keep --all` first, stopping if it fails, and removing `/etc/porelo-host/store/` at
  its end;
- the units, the tests and the documents.

This issue waits on porelo's issue, and the measured round trip waits on a test bucket and its keys from the operator.
