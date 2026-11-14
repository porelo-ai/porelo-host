# HO40 — The Build Runs On The Host's Forge As On GitHub

```json
{
  "$schema": "issue-1.json",
  "id": "HO40",
  "title": "The Build Runs On The Host's Forge As On GitHub",
  "state": "Backlog",
  "size": "M",
  "priority": "Medium",
  "rank": 1,
  "blockedBy": [],
  "covers": "The move's builds on the host's forge: `build.yml` green on the host's Forgejo and on GitHub unchanged, with task branches built, the tools without `podman run`, snapshots by variable and Molecule on a machine with KVM."
}
```

**Why this size.** three workflows and the tools' Maven pom changed alike for two forges, each leg seen red on a host's
Forgejo first, run on a rehearsal VM's forge and on GitHub on the same commit.

**What must be true.** This repository's workflows run unchanged and green on the host's Forgejo and on GitHub, the
differences only in variables both forges carry, with the values of
[the local registry and publication settings](../doc/local-forge.md#the-local-registry-and-publication-settings), so that
`Agent Host` in its task ([HO39](README.md#ho39)) has a build to read for its push.

## Plan

Read in today's `build.yml`, `release.yml`, `shared-rules.yml`, `build/tools.sh`, `build/pom.xml` and the forge role's
runner, against porelo-message-sluice's workflows, which already run on both.

- **`build.yml`'s `push` takes every branch** (`branches: ['**']`, as porelo-message-sluice's), so a task's branch
  builds on its push, before any pull request.
- **The tools without `podman run`.** The `build` job runs in the tools image `build/tools-image` pins, as a job
  container on both forges, with `HOST_TOOLS_IN_IMAGE` set, so `build/tools.sh` runs each tool directly there as it does
  in a task. A job container on the forge's runner cannot start podman, and GitHub's runner then needs none either.
  `build/tools.sh` already runs a tool directly under `HOST_TOOLS_IN_IMAGE`; the workflow alone changes.
- **The `pinned-jdk` action in the job container.** It starts the shared tools with the runner's `JAVA_HOME_25_X64`,
  which the tools image does not carry; the job container gets the pinned GraalVM by digest, as `porelo.yml`'s image
  adds it, and the action stops in words where no Java is there. Its GitHub token goes only to
  `https://github.com` already.
- **The shared tools' snapshots by variable.** `build/pom.xml` names its snapshot repository by `MAVEN_SNAPSHOTS_URL`
  and reads it with `PORELO_PACKAGES_READ_TOKEN` through a settings file the `pinned-jdk` action passes, as
  porelo-message-sluice's do. On GitHub the variable is Sonatype's address, read anonymously; on the forge it is the
  forge's registry. The step stops in words where either is empty.
- **Molecule.** It needs KVM, systemd and libvirt, which a job container on the forge's runner lacks. The `molecule`
  job runs only where `github.server_url` is `https://github.com`, both legs of its `kvm` matrix; GitHub's run is the
  one that counts.
- **`release.yml`** creates its GitHub release with `gh` on a `v*` tag. It runs only where `vars.PORELO_PUBLISH` is
  `true`, so a tag on the host's forge publishes nothing and fails nothing. Publishing stays central.
- **`shared-rules.yml`** needs no change: its scheduled step reads `main`'s commits from the checkout, not from GitHub's
  API, and its pull-request step reads the server from `github.server_url`.
- **Red first:** today's `build.yml` on a rehearsal VM's forge (`build/rehearse-move.sh`), with porelo-host in the
  organization's project: it fails at `podman` and at the snapshot repository. Then the changed workflows green there
  and on GitHub on the same commit.

## Acceptance

- `build.yml` runs green on the host's Forgejo and on GitHub on the same commit, its `molecule` job run on GitHub and
  skipped on the forge.
- Seen to fail first: today's `build.yml` on the host's Forgejo.
- A `v*` tag on the host's forge starts no release that fails.

## Answered by the operator

- **Molecule on the forge:** skipped there; GitHub's run is the one that counts, and this issue stays M (operator,
  2026-11-06).

## To be checked

- That the forge's runner and GitHub both run `actions/checkout` and the `pinned-jdk` action inside the tools image as
  a job container (Node in the image; the runner's GraalVM volume).
- The `build` job's 20 minutes on the forge's share of a core: the unit suite alone takes about 3 minutes on 16
  threads here. Measured on the rehearsal VM; the limit is raised in the same workflow if it does not hold.
