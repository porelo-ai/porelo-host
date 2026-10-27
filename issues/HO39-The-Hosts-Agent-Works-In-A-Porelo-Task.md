# HO39 — The Host's Agent Works In A Porelo Task

**Status:** Idea.

**What must be true.** porelo-host's own agent, `Agent Host` in the project's room, works in a Porelo task on the
move's host as porelo-project [PJ59](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj59) lays
out for sprint 8a, with a way back to this machine at any time, since a fault in the host's setup can stop its own work.

## Acceptance

- The task follows `porelo-host` through the gate, its pushes reach the host's Forgejo, and the build there is green
  and read through the `forgejo` reader.
- This issue is taken from start to Review inside the task, and the agent is reached in the room as `Agent Host`,
  from the nickname `Host` in porelo-project's `project.yml`.
- The way back is shown once: the task's open work fetched from the host's forge into this machine's checkout, the
  upstream switched back, the local session resumed, as the move's step 5 says.

## To be checked

- **The repository alone moves.** `porelo-buildtools`, kept by the same agent today, moves on its own in sprint 7, by an
  issue of that repository's own.
- **The task's image** is `porelo.yml`'s: the Ansible tools image by digest with the pinned GraalVM, in which
  `build/tools.sh` runs each tool directly. The checkout brings the unit tests and the tarball's sources, and
  `./mvnw -f build/pom.xml` fetches the documents' checks at run time.
- **`build.yml` does not run on Forgejo as it is**, and what it needs there is a change of this repository's own,
  perhaps an issue like porelo-project's [PJ60](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj60):
  - its `push` builds `main` only, so a task's branch builds nothing until its pull request;
  - its `build` job runs the tools through `build/tools.sh`'s `podman run`, which a job container of the forge's
    runner cannot;
  - the shared tools' snapshots come from Sonatype by a URL `build/pom.xml` names, not from `MAVEN_SNAPSHOTS_URL`;
  - its Molecule leg needs KVM, systemd and libvirt on Ubuntu 26.04, which the forge's runner image lacks; a VM of the
    host's pool ([HO12](README.md#ho12)) may give them.
- **What the task's container cannot do:** it has no KVM or libvirt, so `build/molecule.sh` and any VM test run only
  through the forge's build or on a VM of their own, and a run that changes the host it runs on, such as `up` or `down`
  on the move's own host, never runs from a task there.
