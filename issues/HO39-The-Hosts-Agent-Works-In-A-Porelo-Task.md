# HO39 — The Host's Agent Works In A Porelo Task

**Status:** Idea.

**What must be true.** porelo-host's own agent works in a Porelo task of the project `porelo` on the move's host, as
porelo-project [PJ59](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj59) lays out for sprint
8a, the last builder beside `porelo`. The task follows this repository through the gate and pushes to the host's
Forgejo, whose build of the collection is read through the `forgejo` reader. The agent is reached in the project's room
under this repository's name. This issue is taken from start to Review inside the task, with the forge's build green.
A way back to this machine stays open at any time, since a fault in the host's setup can stop the agent's own work.

## What moves, and what to check

- **The repository:** `porelo-host` alone. `porelo-buildtools`, today kept by the same agent, moves on its own in sprint
  7, by an issue of that repository's own.
- **The task's image:** this repository's `porelo.yml`, the Ansible tools image by digest with the pinned GraalVM, so
  `build/tools.sh` runs each tool in the image itself. It holds the linters, `black`, the unit tests, the tarball and
  the documents' checks.
- **Forgejo's build:** `build.yml` runs unchanged there. Its Molecule leg makes a libvirt VM with nested KVM, which a
  task's container cannot, so it needs a runner with KVM: the forge's runner, or a VM of the host's pool
  ([HO12](README.md#ho12)). Which of the two, is measured before the move.
- **The way back:** the task's open work is fetched from the host's forge into this machine's checkout, the
  repository's upstream switches back in `project.yml`, and the local session resumes with its watcher, as the move's
  step 5 says.
- **What a task cannot do here:** a run that changes the host it runs on, such as `up` or `down` on the move's own
  host, never runs from inside a task there. Each is a test on a VM of its own.
