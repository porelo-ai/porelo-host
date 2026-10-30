# HO65 — The Host's Tunnel Addresses Answered

**Status:** Idea.
**Replaced:** by the project's one-click joining: the host has no tunnel addresses any more. Proposed to the operator as
Rejected.

**What must be true.** A project admin's account asks the host, read-only and without secrets, which `wg-porelo`
addresses it uses: its own, the host admin's peers and every project's peers. The interface proposes a laptop
address outside them.

## Why

Walk 23: the Developers dialog proposed 10.73.1.2, the host admin's own laptop peer. The access file does not know the
host admin's peers, so the proposal and its check accepted it; the host's sync then refuses it.

## To be checked

- Whether it is a new `porelo-host-person` act behind sudo, like `sync`, and its JSON.
- That it names addresses only, never a key or a person outside the caller's projects.
