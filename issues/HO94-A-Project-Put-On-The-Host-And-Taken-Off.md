# HO94 — A Project Put On The Host And Taken Off

**Status:** Backlog.
**Size:** M - the follow's handling of the host's projects, today's project helper behind it, the migration with the
host admin's token, Molecule.

**What must be true.** When the host admin puts a project on the host, its forge organization, publisher and
repositories stand on the host's forge at once, and every member of the project is admitted; when the host admin takes
it off, it goes once nothing of it is unpushed, and each member with no other membership is locked.

## Plan

- The host's card in the organization names the projects it carries by name; the follow compares that list with the
  projects the host has and puts on or takes off the difference.
- Putting on: `roles/forge/files/porelo-host-project add` as today, with the signer from the project's `project.yml`
  as the organization hands it; then the repositories migrate from the central forge with the host admin's central
  token, sent once through their tunnel on standard input, as the push takes it today; it never lies on the host.
- Taking off: `porelo-host-project remove` as today, refused while any repository holds a commit the central forge
  lacks, with the refusal named in the follow's answer.
- The project's room: on putting on, on each change of its members and on *Refresh*, the follow runs the Matrix
  gate's `keep-room --project <project> --persons <logins>` with the members' logins, and tries a 75 again at the
  next follow. No admins file is written under `/etc/porelo-host/matrix/` any more.
- Taking off also deletes the project's room on this host with its conversation: once the project is gone, the
  follow runs the gate's `drop-room --project <project>`, which takes every member out; a 75 is tried again at the
  next follow, a 78 (a room under the alias the gate's administrator did not make) is named in the follow's answer
  and left alone. A project on two hosts has a room on each, and taking it off one leaves the other's.
- Red first: a project the card no longer names, holding an unpushed commit, stays and is named; one taken off has
  its room dropped.

## Acceptance

- Molecule: a project put on the card stands with its repositories after one follow; taken off, it goes, or stays
  named while a commit is unpushed.

## To be checked

- How the interface sends the host admin's token at the moment of putting on: the same stop as the push, or one of
  its own.
- Where Porelo on the host takes its transport's `homeserver` and `room` from, now that no access file names them:
  settled with Core.
