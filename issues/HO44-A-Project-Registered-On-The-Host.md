# HO44 — A Project Registered On The Host

**Status:** Review.
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
- **`remove <project>`:** refused while any repository holds a commit the central forge lacks; then the organization
  with its repositories and packages and the publisher are deleted. Only unpushed work stops it (operator,
  2026-10-29). In this issue no repository reaches the host, so `remove` takes off an organization with none and
  refuses one that holds any; comparing with the central forge comes with the project admin's bring.

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
- **`remove`'s central token,** asked only while the organization holds a repository: the first and only line of standard
  input when it is no terminal, as the interface pipes it from the host admin's secrets file; a prompt that shows
  nothing at a terminal. Until the bring, a repository is refused, so a copy never compared is never deleted.
- **The bring and `remove`** (agreed with Agent Frontend and Agent Core, 2026-10-29): the bring loads each repository
  as a Forgejo migration from the central forge, which keeps its `original_url`; `remove` compares each repository with
  that URL and needs nothing more from the interface than the token. The account's `default` project lives on no
  host forge, so `remove` never meets it.

## Acceptance

- Molecule: two projects registered for two admins, each organization owned by its admin alone; a build of one cannot
  publish into the other's packages; `remove` green for an organization with no repository, and refused for one that
  holds a repository. Refused with an unpushed commit, then green once pushed, is the bring's Acceptance.
