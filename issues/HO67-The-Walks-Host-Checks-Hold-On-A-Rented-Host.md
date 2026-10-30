# HO67 — The Walk's Host Checks Hold On A Rented Host

**Status:** Idea.
**Replaced:** by the project's one-click joining: the walk's VPN and token checks go; the guide is rewritten in
[HO74](README.md#ho74). Proposed to the operator as Rejected.

**What must be true.** The guide's host checks (`doc/guides/6-host.md` and its scripts) pass on a rented host
without hand patches, and the host runs the porelo-host the walk names.

## Why

Walk 23:

- `on_forge` in `6-host-lib.sh` had no session bus (see [HO63](README.md#ho63)).
- `host-sync.6` read `/users/<developer>` with the forge's API token, which has no `read:user` scope: 403
  `tokenRequiresScopes`.
- walk9server ran a `porelo-host-person` older than e6bdb97, so the purge refused until a current copy was deployed by
  hand. Nothing checked which porelo-host the host ran.

## To be checked

- How `host-sync.6` reads `prohibit_login` without widening the forge token's scopes, e.g. Forgejo's own command line
  in the container.
- That `host-prepare` checks the installed collection and helpers against the porelo-host commit the walk names.
