# HO87 — The Host's Registry State Answered

**Status:** Backlog; blocked by [HO70](README.md#ho70).
**Size:** S - one read-only verb and two fields of the registry's answer, from records the helper reads already.

**What must be true.** The interface learns, over SSH as root with the card's key alone, which registry the host
applied and where each person stands on it, without reading root's files itself.

- `porelo-host-person registry status`, root's alone and read-only, answers one JSON line: `host`, the applied
  `commit`, the `pinned` fingerprint, and `persons`, each with `login`, `state` (`active`, `locked`, `pending`,
  `purged`, or `named` for a login the registry names that the host has not admitted), `hand` and `projects`
  (`project`, `role`), sorted by login.
- `registry` and `registry --stdin` answer `host` and `persons` too, in that shape, read after the bundle is applied;
  their other fields stay.
