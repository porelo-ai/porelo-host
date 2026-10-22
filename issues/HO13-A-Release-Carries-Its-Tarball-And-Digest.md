# HO13 — A Release Carries Its Tarball And Digest

**Status:** Backlog.
**Size:** S - one workflow on a tag, and the tarball and its digest attached; no role changes. The check on the
person's computer is porelo-frontend's.

**What must be true.** A release of the collection attaches `porelo-host-<version>.tar.gz` and a `SHA256SUMS` naming
its digest, so `host up` can take exactly that tarball and refuse any other before it is copied or installed.

## Plan

- **Why:** the host installs the tarball with Ubuntu's `ansible-core`, whose CVE-2026-89091 lets a crafted tarball
  write outside its directory; the decision in `doc/decisions.md` accepts that only because the tarball is ours. A
  digest the release names makes "ours" checkable.
- **`.github/workflows/release.yml`**, on a tag `v<version>` matching `galaxy.yml`'s version: the tarball built by
  `build/tools.sh ansible-galaxy collection build` and refused by `build/check-tarball.sh` as in the Build, its
  `SHA256SUMS` written beside it, both attached to the GitHub release; `contents: write` in that job alone, every
  action pinned by commit.
- **A tag whose version is not `galaxy.yml`'s** stops the workflow before anything is built, naming both.
- **porelo-frontend's part** is its own issue: `host up` pins the digest of the release it is built against, refuses
  a tarball that does not match, and checks it again on the host before `ansible-galaxy collection install`.
- **`doc/decisions.md`'s accepted risk for CVE-2026-89091** gains, once this is built, that a release names the
  tarball's digest and `host up` checks it.
- **Red first:** the workflow's version check run against a tag that does not match must stop, naming both versions.

## Acceptance

- A release made from a tag carries the tarball and its `SHA256SUMS`, and `sha256sum -c SHA256SUMS` passes on the
  downloaded pair.
- A mismatched tag stops the workflow before anything is attached.

## To be checked

- **The tarball is not reproducible as built today:** the collection built twice from the same commit `9edc14a` on
  2026-10-19 gave two SHA-256s (`a3760efa…` at 13:38Z, `4b209775…` at 14:03Z), likely the times in the tar. So a
  digest pinned per release means something only for the one tarball the release builds and attaches; whether
  `ansible-galaxy collection build` can be made reproducible (fixed times, sorted entries) is to be read, and either
  way a person's `host up` takes the release's own file, never one built again.

- Which version the first release takes: `galaxy.yml` says `0.5.1-snapshot`, while a release needs a plain
  semantic version matching Porelo's.
