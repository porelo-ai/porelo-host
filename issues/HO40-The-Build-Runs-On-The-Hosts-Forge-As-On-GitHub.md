# HO40 — The Build Runs On The Host's Forge As On GitHub

**Status:** Idea.

**What must be true.** This repository's workflows run unchanged and green on the host's Forgejo and on GitHub, the
differences only in variables both forges carry, as porelo-project
[PJ60](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj60) asks of every repository, so that
`Agent Host` in its task ([HO39](README.md#ho39)) has a build to read for its push.

## Acceptance

- `build.yml` runs green on the host's Forgejo and on GitHub on the same commit.
- Seen to fail first: today's `build.yml` on the host's Forgejo.

## To be checked

- **What fails today on the host's Forgejo, read in `build.yml` and `roles/forge/`:**
  - its `push` builds `main` only, so a task's branch builds nothing until its pull request;
  - its `build` job runs the tools through `build/tools.sh`'s `podman run`, which a job container of the forge's
    runner cannot, while a task's image has them directly (`HOST_TOOLS_IN_IMAGE`);
  - the shared tools' snapshots come from Sonatype by a URL `build/pom.xml` names, not from `MAVEN_SNAPSHOTS_URL`;
  - its Molecule leg needs KVM, systemd and libvirt on Ubuntu 26.04, which the forge's runner image lacks; a VM of the
    host's pool ([HO12](README.md#ho12)) may give them, by a kind both forges serve.
- **`release.yml` and `shared-rules.yml`:** neither reads `PORELO_PUBLISH` today; publishing a release stays central,
  switched by that variable on both forges, never by a branch in the workflow, and how the daily check runs on the
  forge is read.
