# HO142 — The Person's Vault Holds Their Forge Token From The Start

**Status:** Implementing.
**Kind:** Bug.
**Size:** S - one place on the host puts the person's `<forge>.person` vault entry, shared with `porelo-host-push`, with
its unit tests.

**What must be true.** Once a person is on the host, their Porelo-Vault holds `<forge>.person`, so anything they run
on the host reads the host's forge over Git as them before their first gathered push.

## Why

Only `porelo-host-push` puts that entry, after `porelo-host-person forge-token` made the token. Admission makes the
forge identity but no token, since the forge keeps only a token's hash. In a trial move the move check and a bundle
of the host's `main` could not read the forge, and the work was taken from the forge's volume by root instead.

## Plan

- The entry is made where the person's vault is first open on the host, by the same helper `porelo-host-push` uses,
  so there is one way of making it; the place is chosen after reading who runs the stop and as which user.
- The token passes only through a pipe, never an argument, a file or output; a failure stops with a reason.
- **Red first:** with stand-ins for `sudo`, `porelo` and the forge, a person whose stop has run holds the entry; red
  on today's code.

## Acceptance

- The unit tests, seen red on today's code and green after.
- On the next move's host, the move check reads the forge as the person before any gathered push.
