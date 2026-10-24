# HO13 — A Release Carries Its Tarball And Digest

**Status:** Review.
**Size:** S - one workflow on a tag, and the tarball and its digest attached; no role changes. The check on the
person's computer is porelo-frontend's.

**What must be true.** A release of the collection attaches `porelo-host-<version>.tar.gz` and a `SHA256SUMS` naming
its digest, so `host up` can take exactly that tarball and refuse any other before it is copied or installed.

## Plan

- **Why:** the host installs the tarball with Ubuntu's `ansible-core`, whose CVE-2026-89091 lets a crafted tarball
  write outside its directory; the decision in `doc/decisions.md` accepts that only because the tarball is ours. A
  digest the release names makes "ours" checkable.
- **`.github/workflows/release.yml`**, on a tag `v*`, in two jobs, so the token that writes never stands beside the
  checkout, the tools image or a fetched action:
  - `build`, reading only: the tag must be `v` and `galaxy.yml`'s version, and that version a plain
    `MAJOR.MINOR.PATCH`, since a release depends only on releases; otherwise it stops, naming what it read. Then the
    tarball built by `build/tools.sh ansible-galaxy collection build` and refused by `build/check-tarball.sh` as in the
    Build, its `SHA256SUMS` written beside it and checked, both uploaded as the run's artifact. The check reads the
    `version:` line, not the YAML; the tarball, which `ansible-galaxy` names from the parsed file, must be
    `porelo-host-<version>.tar.gz`, so a version the line misreads stops before anything is attached.
  - `publish`, `contents: write` and `actions: read` alone, no checkout and no `uses:`: the artifact fetched with the
    runner's `gh` by the id this attempt's build uploaded, since a re-run keeps the earlier attempt's artifact under the
    same name; `sha256sum -c` run on it, refused unless it holds exactly the tarball and `SHA256SUMS`, then
    `gh release create --verify-tag`, which fails on a release that already exists.
- **The digest names the one tarball the release builds and attaches:** the tarball is not reproducible (the same
  commit built twice gave two digests), so a person's `host up` takes the release's own file, never one built again.
- **porelo-buildtools:** `check-actions` lets exactly `release.yml`'s job `publish` write `contents`, and only while it
  runs no fetched action or checkout; this repository's Build runs that check, so this change is pushed after
  porelo-buildtools' has built and published.
- **porelo-frontend's part** is its own issue, porelo-frontend
  [F137](https://github.com/porelo-ai/porelo-frontend/blob/main/issues/README.md#f137), which this one blocks: `host up`
  brings the matching collection or fetches it from this repository's release, pins its digest, refuses a tarball that
  does not match, and checks it again on the host before `ansible-galaxy collection install`.
- **`doc/decisions.md`'s accepted risk for CVE-2026-89091** says that a release names the tarball's digest.
- **Red first:** the version check, run as the workflow's own script, against a snapshot version, a tag that does not
  match, and a `galaxy.yml` with no or two `version:` lines, each stopping and naming what it read; the publish step,
  with `gh` stood in, refusing an artifact with a file more, a dot file, a link or a changed tarball, and a build that
  named no artifact id.

## Acceptance

- A release made from a tag carries the tarball and its `SHA256SUMS`, and `sha256sum -c SHA256SUMS` passes on the
  downloaded pair.
- A mismatched tag stops the workflow before anything is attached.
- The first release is made by the operator: `galaxy.yml`'s version set to a plain version, then its tag pushed.
