# HO94 — A Project Put On The Host And Taken Off

**Status:** Backlog.
**Size:** M - the follow's handling of the host's projects, today's project helper behind it, the migration with the
host admin's token, Molecule.

**What must be true.** A project is on one host at a time. When the host admin puts a project on the host, every
member of the project is admitted, and where the host runs a forge, the project's forge organization, publisher and
repositories stand on it at once; when the host admin takes it off, it goes once nothing of it on that forge is
unpushed, and each member with no other membership is locked. Nothing of it needs a forge or a homeserver on the host:
a host without them takes and drops the project's members alone.

## Plan

- The host's card in the organization names the projects it carries by name; the follow compares that list with the
  projects the host has and puts on or takes off the difference.
- Putting on, where the host runs a forge: `roles/forge/files/porelo-host-project add` as today, with the signer from
  the project's `project.yml` as the organization hands it; then the repositories migrate from the central forge with
  the host admin's central token, sent once through their tunnel on standard input, as the push takes it today; it never
  lies on the host. The same token adds the host's read-only deploy key to each of the project's repositories; the key
  is made on the host, root's alone, and taking the project off removes it.
- Taking off, where the host runs a forge: `porelo-host-project remove` as today, refused while any repository holds a
  commit the central forge lacks, read with the project repository's deploy key, with the refusal named in the follow's
  answer.
- The project's room, where the host runs the Matrix gate and the project's `project.yml` names no homeserver of its own
  under `mail.transports.matrix` (otherwise its room is kept where it names, not here): on putting on, on each change of
  its members and on *Refresh*, the follow runs the Matrix gate's `keep-room --project <project> --persons <logins>`
  with the logins of the members not locked, and tries a 75 again at the next follow. No admins file is written under
  `/etc/porelo-host/matrix/` any more.
- Taking off also deletes, under the same condition, the project's room on this host with its conversation: once the
  project is gone, the follow runs the gate's `drop-room --project <project>`, which takes every member out; a 75 is
  tried again at the next follow, a 78 (a room under the alias the gate's administrator did not make) is named in the
  follow's answer and left alone.
- Red first: on a host with no forge, a project put on admits its members and takes nothing else; a project the card no
  longer names, holding an unpushed commit on the host's forge, stays and is named; one taken off has its room dropped.

## Acceptance

- Molecule: a project put on the card stands with its repositories after one follow; taken off, it goes, or stays named
  while a commit is unpushed.

## To be checked

- How the interface sends the host admin's token at the moment of putting on: the same stop as the push, or one of its
  own.
- Where Porelo on the host takes its transport's `homeserver` (`unix:/run/porelo-matrix/client.sock`) and `room`
  (`#porelo-<project>:<server>`, with the host's Matrix server name) from, both always, now that no access file names
  them: a file the host writes, settled with Core.
