# HO115 — The Pool VM Not Ready On GitHub's Runner

**Status:** Idea.

**What must be true.** The pool's VM says ready within its 15 minutes on GitHub's runner, or the reason it cannot is
known, so a Build there may check the pool again.

## Why

On GitHub's runner (AMD, nested KVM present) the pool VM gets its address but does not say ready within 15 minutes
(porelo-host Builds 16 and 17). Nobody has found why. So the Build sets `PORELO_HOST_MOLECULE_POOL=off`, and **GitHub
therefore does not check the pool:** a change that breaks it stays green there, and only a local Molecule run shows it.
The pool's own acceptance does not wait on this.

## Acceptance

- The reason is named, with the log that shows it. Seen to fail: a run on that runner that stops at the pool VM's ready
  check, read before the change.
- Either the Build runs Molecule with the pool on and it passes there, or this issue says why that runner cannot, and
  the pool stays checked elsewhere.
