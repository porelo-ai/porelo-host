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
- The room's admins file is written from the project's members with their role.
- Red first: a project the card no longer names, holding an unpushed commit, stays and is named.

## Acceptance

- Molecule: a project put on the card stands with its repositories after one follow; taken off, it goes, or stays
  named while a commit is unpushed.

## To be checked

- How the interface sends the host admin's token at the moment of putting on: the same stop as the push, or one of
  its own.
