# HO47 — The Gathered Push Run By Any Developer

**Status:** Review.
**Size:** S - `porelo-host-push` turned from a root tool with one config into a user tool reading the person's
own config and token.

**What must be true.** Every developer of a project, not only its admin, pushes the project's repositories from the
host's forge to the central forge with their own write token (QH62 b).

## Why

Any developer of a project runs the gathered push. Today it is root's, configured once per host for the one person.

## Plan

- `porelo-host-push <project>` reads `~/.config/porelo-host/push/<project>.conf` (written by
  [HO45](README.md#ho45)) and the person's own write token from their own vault, never from a root file; the
  local forge is read with their own forge token.
- `porelo-host-project remove <project>` stops reading the central addresses from root's
  `/etc/porelo-host/forge/push.conf`, which the bring no longer writes: it compares each repository with the
  `original_url` Forgejo kept from the migration (Coordinator, room 2026-10-29).

## Acceptance

- Molecule: a developer and the project admin each push with their own token; another person's config is not
  readable; no token in the output or the journal.
