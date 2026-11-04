# HO114 — A Host's Read Keys Taken Off The Central Forge

**Status:** Idea.

**What must be true.** Taking a project off a host, and `down`, delete the host's read-only deploy keys at the central
forge, with a token asked once and kept nowhere. Where that is impossible, each key is named with a link to where its
repository's owner removes it. This is the host's side; the interface asks the token in the
window.

## Why

Today nothing deletes them. `porelo-host-project remove` deletes the private halves and names each public one in
`left_at_central`, by address and title; the follow, with no central token at hand, writes that to its journal. `down`
removes `/etc/porelo-host/organization`, the organization's read key with it, and names nothing.
[`doc/local-forge.md`](../doc/local-forge.md) says so and leaves them to the repository's owner by hand.

## Acceptance

- A project taken off with the token given: its repositories' keys of this host are gone at the central forge. Seen to
  fail: listed there after the removal.
- `down` with the token given: the organization's read key of this host is gone too.
- With no token, or a token that may not delete them: each key is named with its link, and nothing stops.
- The token appears in no file, command line or log.

## To be checked

- How the token reaches a follow that takes a project off with nobody there: `org refresh`'s standard input, as the first
  migration has it, then needs the left keys' public halves or ids kept after the removal, or a project taken off waits.
- A key of another host, and one of an earlier title, stay, as the helper already keeps them.
