# HO44 — A Project Registered On The Host

**Status:** Estimated.
**Size:** M - a root helper making and deleting one forge organization with its publisher, the pinned signing
key, and the refusal while anything is unpushed.

**What must be true.** The host admin registers a project for its admin with the project's signing key, and takes it
off again once nothing of it is unpushed; one forge organization and one publisher per project.

## Why

A project is put on a host apart from the host itself. Making a forge account needs the forge's admin, so the organization and its publisher are root's (QH55 a,
QH54 a); a publisher per project keeps one project's builds from publishing into another's.

## Plan

- **`porelo-host-project add <project> <admin> --signed-by <key>`** (root): the organization named by the project,
  the admin in its Owners; `porelo-publisher-<project>` with a team writing only that organization's packages and its
  token as the organization's secret `PORELO_PUBLISHER_TOKEN`; `projects/<project>.conf` with the admin and the pinned
  key. A name already taken is refused.
- **`remove <project>`:** refused while any repository holds a commit the central forge lacks, read with the gathered
  push's own comparison; then the organization with its repositories and packages and the publisher are deleted.

## The contract with the interface

- **`--signed-by`** is the project's signing key as Porelo's `signers` name it: one argument `ssh-ed25519 AAAA…` with no
  comment.
- **On success** one JSON line on stdout: `add` answers
  `{"project":"…","admin":"…","organization":"…","publisher":"porelo-publisher-<project>"}`, `remove`
  `{"project":"…","removed":true}`.
- **A refusal** goes to stderr as `porelo-host-project: <words>`, with nothing changed and exit 64 (input), 65 (the
  records or the forge say no: a name taken, a commit unpushed), 69 (something needed is missing or not root's) or 73
  (cannot write).
- The interface runs it as `ssh root@10.73.<n>.1 /usr/local/sbin/porelo-host-project …` with the rental's key.

## Acceptance

- Molecule: two projects registered for two admins, each organization owned by its admin alone; a build of one cannot
  publish into the other's packages; `remove` refused with an unpushed commit, then green once pushed.
