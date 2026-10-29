# HO39 — The Host's Agent Works In A Porelo Task

**Status:** Idea; blocked by [HO40](README.md#ho40).

**What must be true.** porelo-host's own agent, `Agent Host` in the project's room, works in a Porelo task on the
move's host as the project's procedure for an agent's move lays out, with a way back to this machine at any time, since a fault in the host's setup can stop its own work.

## Acceptance

- The task follows `porelo-host` through the gate, its pushes reach the host's Forgejo, and the build there is green
  and read through the `forgejo` reader.
- This issue is taken from start to Review inside the task, and the agent is reached in the room as `Agent Host`,
  from the nickname `Host` in porelo-project's `project.yml`.
- The way back is shown once: the task's open work fetched from the host's forge into this machine's checkout, the
  upstream switched back, the local session resumed, as that procedure's way back says.

## To be checked

- **The repository alone moves.** `porelo-buildtools`, kept by the same agent today, moves on its own, earlier, by an
  issue of that repository's own.
- **The task's image** is `porelo.yml`'s: the Ansible tools image by digest with the pinned GraalVM, in which
  `build/tools.sh` runs each tool directly. The checkout brings the unit tests and the tarball's sources, and
  `./mvnw -f build/pom.xml` fetches the documents' checks at run time.
- **The build on the host's Forgejo** is [HO40](README.md#ho40)'s: `build.yml` does not run there as it is.
- **What the task's container cannot do:** it has no KVM or libvirt, so `build/molecule.sh` and any VM test run only
  through the forge's build or on a VM of their own, and a run that changes the host it runs on, such as `up` or `down`
  on the move's own host, never runs from a task there.
