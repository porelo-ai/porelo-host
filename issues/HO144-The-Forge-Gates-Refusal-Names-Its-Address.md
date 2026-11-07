# HO144 — The Forge Gate's Refusal Names Its Address

**Status:** Implementing.
**Kind:** Bug.
**Size:** XS - the 403 for a foreign `Host` in `porelo-forge-gate` says which address to use, with its unit test.

**What must be true.** A person who opens the forwarded forge under another name than its own reads, in the refusal,
the address that works.

## Why

In a trial move the forwarded forge answered a bare 403 to `localhost:3000` and 200 to `127.0.0.1:3000`, with no word
why. The gate takes only the forge's own name or `127.0.0.1`, so that no other site in the browser can act as the
person through a name that resolves to the loopback; that stays.

## Plan

- The refusal for a foreign `Host` carries a short text body naming `http://<forge name>:<port>/` and
  `http://127.0.0.1:<port>/`, the port the request came to; no other refusal changes.
- **Red first:** the gate's unit test for a foreign `Host` asserts the body names the forge's address; red today.

## Acceptance

- The unit test, seen red on today's gate and green after.
