# HO47 — The Gathered Push Run By Any Developer

**Status:** Estimated (Accepted by the operator, 2026-10-28; estimated the same day).
**Size:** S - `porelo-host-push` turned from a root tool with one config into a user tool reading the person's
own config and token.

**What must be true.** Every developer of a project, not only its admin, pushes the project's repositories from the
host's forge to the central forge with their own write token (QH62 b).

## Why

[PJ78](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj78). Today the gathered push is root's, configured once per host for the one person.

## Plan

- `porelo-host-push <project>` reads `~/.config/porelo-host/push/<project>.conf` (written by
  [HO45](README.md#ho45)) and the person's own write token from their own vault, never from a root file; the
  local forge is read with their own forge token.

## Acceptance

- Molecule: a developer and the project admin each push with their own token; another person's config is not
  readable; no token in the output or the journal.
