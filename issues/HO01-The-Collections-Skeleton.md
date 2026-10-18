# HO01 — The Collection's Skeleton

**Status:** Implementing.
**Size:** M - a collection's metadata, its lint configuration, a workflow, the documents' checks and a check of what
the tarball holds; no role yet, but the shape every later issue builds in.

**What must be true.** `porelo.host` builds as an Ansible collection with `ansible-galaxy collection build` into a
tarball that holds only what it ships, passes `yamllint` and `ansible-lint` in its production profile, and its Build
checks that on every push, on a GitHub runner, with no rented machine. A person installs it with
`ansible-galaxy collection install` and reads in its README which `ansible-core`, which systems and which Porelo
version it needs.

## Plan

- **The collection at the repository root**, so `galaxy.yml` sits beside `README.md`: `galaxy.yml` (namespace
  `porelo`, name `host`, version `0.5.1-snapshot` following Porelo's, license GPL-3.0-or-later as `LICENSE` is, the
  repository's URL), `meta/runtime.yml` with `requires_ansible: ">=2.19.0"` (the newest `ansible-lint` accepts),
  `roles/` and `playbooks/` holding a `.gitkeep` until the first role. YAML there is two spaces, as `.editorconfig`
  says.
- **Decided**: the Ansible tools run from one container image pinned by digest, through podman, the same here and in
  the Build; nothing is installed on this machine. The collection ships as a tarball on the repository's GitHub
  releases; Galaxy comes later, once others use it. The playbook supports Ubuntu 26.04 at first; Fedora is an issue of
  its own.
- **The image** is the published `ghcr.io/ansible/community-ansible-dev-tools` `v26.10.1`, by its digest, in
  `build/tools-image` (`ansible-core` 2.21.5, `ansible-lint` 26.10.1, `molecule` 26.10.0, `yamllint` 1.38.0);
  `build/tools.sh` runs a tool from it on the checkout, as the calling account, and refuses a reference without a
  digest.
- **No sample content**: no `run` role, no sample plugins; `ansible-creator` is not used.
- **The changelog stays `CHANGELOG.md`, Keep a Changelog**, as in every Porelo repository; no `antsibull-changelog`.
- **The tarball holds only what ships**: `build_ignore` leaves out the repository's own work and every dot file, at
  the top and below it, and `build/check-tarball.sh` refuses a tarball with any entry outside `meta/`, `roles/`,
  `playbooks/`, `plugins/`, `README.md`, `LICENSE`, `CHANGELOG.md` and Ansible's two manifests, any dot file, or none
  of `meta/runtime.yml`, `README.md` and `LICENSE`. Seen red: a build from this checkout first held `.AGENTS.md`,
  `.idea/` and `.claude/`.
- **The lint configuration** is in `build/`, not in dot files: `ansible-lint.yml` (profile `production`), and two for
  `yamllint`, run with `--strict`, since it reports a `yes` as a warning only: `yamllint-ansible.yml` holds
  `roles/`, `playbooks/`, `molecule/`, `extensions/` and `galaxy.yml` to two spaces, `yamllint.yml` every other YAML
  file to four with sequences indented, as `.editorconfig` splits them and every other repository's workflows are
  written. The workflows run on `ubuntu-24.04`, pinned, as the other repositories' do.
- **`ansible-test sanity` is left out** until the collection holds Python: its tests are for modules and plugins,
  which the collection has none of, and it installs its own requirements from PyPI at run time by version without a
  hash, which a pinned build may not.
- **The Build** (`.github/workflows/build.yml`): on a push to `main` and a pull request, not for a change to
  `.github/` alone, on `ubuntu-latest`: the shared build tools by `build/pom.xml` and `mvnw`, `check-shared AGENTS.md
  .editorconfig`, `check-citations .`, `check-doc-site doc mkdocs.yml`, `check-actions .github`, then `yamllint`,
  `ansible-lint` and the tarball with its check. Plus `.github/dependabot.yml` for the actions, `CODEOWNERS`, and the
  *Shared rules check* on its daily schedule.
- **`check-readmes`** has nothing to check, as there is no `pom.xml` at the root; `build/` has its README all the
  same.
- **Red first**: a role file with a short module name and one with `yes` as a boolean, each seen to fail
  `ansible-lint`, and the `yes` to fail `yamllint --strict`; a two-space file under `build/` and a four-space role
  file, each seen to fail its `yamllint` settings; then removed.

## Acceptance

- [x] `ansible-galaxy collection build` makes `porelo-host-0.5.1-snapshot.tar.gz`, and `build/check-tarball.sh`
  passes on it; it refused the tarball holding dot files, one lacking `README.md`, and an empty one.
- [x] `yamllint --strict` and `ansible-lint` (production) pass on the skeleton, and fail on the planted faults.
- [x] The documents' checks pass locally against porelo-release 0.5.1-SNAPSHOT, `check-actions .github` among them.
- [ ] The Build runs green on GitHub without renting a machine.
