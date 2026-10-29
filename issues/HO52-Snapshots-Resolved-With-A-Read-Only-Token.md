# HO52 — Snapshots Resolved With A Read-Only Token

**Status:** Analyzed; blocked by [HO44](README.md#ho44).
**Size:** M - one contract other repositories read (a secret's name and scope, a variable), in one helper with its
tests and a Molecule act.

**What must be true.** A build on the host's forge resolves its project's snapshots with a token that can only read
them, so a test in an unreviewed task branch can neither overwrite a snapshot nor publish one; only the step that
deploys on `main` holds the publisher's token. Every project organization names its own snapshot registry, so a
build that misses it fails instead of resolving elsewhere.

## Plan

- **The contract** (operator's decision, 2026-10-29; the names are fixed in the room):
  - Actions secret **`PORELO_PACKAGES_READ_TOKEN`** of each project's organization: a Forgejo token with the single
    scope `read:package`, of that organization's publisher account. It reads the organization's packages and nothing
    else.
  - Actions secret `PORELO_PUBLISHER_TOKEN` as today, `write:package`, for the deploying step alone.
  - Actions variable **`MAVEN_SNAPSHOTS_URL`** of each project's organization, `https://<forge>/api/packages/<project>/maven`
    at the address a job reaches, with the other variables a build reads on this forge (`PORELO_PUBLISH`,
    `PORELO_DEPLOY_PROFILE`, `JF_URL`) and the placeholder secret `JF_ACCESS_TOKEN`, as the role set them for one owner
    before [HO42](README.md#ho42).
- **`roles/forge/files/porelo-host-project`, `add`:** after the publisher's token, a second `token(…, publisher,
  "read:package")` put as `PORELO_PACKAGES_READ_TOKEN`, then the variables and the placeholder secret, all inside the
  existing rollback, so a refused `add` leaves none of them. The answer on stdout stays as the contract says; no
  token is printed.
- **Tests first** in `tests/unit/roles/test_porelo_host_project*.py`: the read token is asked with exactly
  `read:package` and put under its name; each variable is set for the project's organization; a failure while setting
  them removes the organization and the publisher. Red before the change.
- **Molecule**, the projects act: with `PORELO_PACKAGES_READ_TOKEN` a generic package of the organization is read
  (200) and a `PUT` into it is refused (not 2xx); with `PORELO_PUBLISHER_TOKEN` the `PUT` succeeds; the organization's
  variables hold `MAVEN_SNAPSHOTS_URL` with its own name.
- `roles/forge/README.md` names both secrets and the variables; `CHANGELOG.md`.

## Acceptance

- Molecule on the VM: the read token reads and cannot write the organization's packages, the publisher's token
  writes, and the organization holds `MAVEN_SNAPSHOTS_URL`; each refusal seen red first; no token in any output or the
  journal.

## To be checked

- Whether Forgejo checks the user name Maven sends against the token's owner; the shared settings send one name for
  every organization's publisher.
- Which address of the forge a runner's job reaches, for `MAVEN_SNAPSHOTS_URL`, now that the forge has its host's
  name.
