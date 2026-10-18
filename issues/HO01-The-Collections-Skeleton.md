# HO01 — The Collection's Skeleton

**Status:** Estimated.
**Size:** M - a collection's metadata, its lint and sanity configuration, a workflow and the documents' checks; no
role yet, but the shape every later issue builds in.

**What must be true.** `porelo.host` builds as an Ansible collection with `ansible-galaxy collection build`, passes
`ansible-lint` in its production profile and `ansible-test sanity`, and its Build checks that on every push, on a
GitHub runner, with no rented machine. A person installs it with `ansible-galaxy collection install` and reads in its
README which `ansible-core`, which systems and which Porelo version it needs.

## Plan

- **The collection at the repository root**, so `galaxy.yml` sits beside `README.md`: `galaxy.yml` (namespace
  `porelo`, name `host`, version matching Porelo's, license GPL-3.0-or-later as `LICENSE` is, the repository's URL),
  `meta/runtime.yml` with `requires_ansible`, `roles/` and `playbooks/` holding a `.gitkeep` until the first role,
  `extensions/molecule/` for [HO03](README.md#ho03). YAML there is two spaces, as `.editorconfig` already says.
- **Decided**: the Ansible tools (`ansible-core`, `ansible-lint`, `yamllint`, `ansible-test`, `molecule`) run from
  one container image pinned by digest, through podman, the same here and in the Build; nothing is installed on this
  machine. The collection ships as a tarball on the repository's GitHub releases; Galaxy comes later, once others
  use it. The playbook supports Ubuntu 26.04 at first; Fedora is an issue of its own.
- **No sample content**: no `run` role, no sample plugins; `ansible-creator` is not used, the few files are written
  by hand against the `ansible-new-collection` skill.
- **The changelog stays `CHANGELOG.md`, Keep a Changelog**, as in every Porelo repository; no `antsibull-changelog`,
  so the changelog has one form. `galaxy.yml`'s `build_ignore` leaves out `issues/`, `doc/`, `mkdocs.yml`,
  `AGENTS.md`, `CLAUDE.md` and the workflow, so the collection's tarball holds only what runs.
- **The lint configuration**: `.ansible-lint` (profile `production`) and `.yamllint`, both excepted in `.gitignore`
  as the shared rule allows for what a build needs.
- **The Build** (`.github/workflows/build.yml`): on a push and a pull request, on `ubuntu-latest`: the shared
  documents' checks (`check-shared AGENTS.md .editorconfig`, `check-citations .`, `check-doc-site doc mkdocs.yml`,
  `check-actions .github`) with `porelo-release` from Central, then `ansible-lint`, `ansible-test sanity` and
  `ansible-galaxy collection build` in the pinned image; every action pinned by commit, and the image's recipe pins
  each Python tool by version and hash. Plus `.github/dependabot.yml` for the actions, weekly, grouped, after three days,
  and the *Shared rules check* workflow on its daily schedule.
- **`check-readmes`** has nothing to check here, since there is no `pom.xml`; this repository is not a Maven
  repository, so it gets no `mvnw` and the tools are fetched by the workflow only.
- **Red first**: a role file with a short module name (`command:` instead of `ansible.builtin.command:`), and one with
  `yes` as a boolean, each seen to fail `ansible-lint` locally and in the Build, then removed.

## Acceptance

- `ansible-galaxy collection build` makes `porelo-host-<version>.tar.gz`, and its file list holds none of
  `issues/`, `doc/` or `AGENTS.md`.
- `ansible-lint` (production) and `ansible-test sanity` pass on the skeleton, and fail on the two planted faults.
- The Build runs green on GitHub without renting a machine; `check-actions .github` passes.

## To be checked

- `porelo-release` 0.5.0's `check-shared AGENTS.md .editorconfig` refuses this repository's `.editorconfig` as
  carrying no shared block; it passes once `porelo-buildtools` publishes the release carrying the two-space YAML
  section. Run again with that release.
- Which image: one built from a pinned recipe here, or a published one by digest; and whether `ansible-test sanity`
  runs inside it under rootless podman.
