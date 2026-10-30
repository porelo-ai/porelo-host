# HO58 — The Services' Podman Kept Small

**Status:** Idea.

**What must be true.** Once a day the host clears the Podman store of each service account, `porelo-forge`,
`porelo-runner` and `porelo-matrix`. It removes the images and volumes that no container has used for a set time, 7
days by default. A run the host missed, because it was off, is made up at the next start.

## Why

The operator found 41 GB of images and 11 GB of volumes on the development machine on the morning of 30 October 2026,
and little used them. porelo-host has no such timer yet, so a host's disk fills the same way with each update of
Forgejo, the runner's job images and Matrix.

## To be checked

- How Podman tells when an image or volume was last used. `podman image prune --filter until=` counts from creation,
  not from last use, and volumes have no such filter.
- Whether a root timer runs it as each account, or each account has a user timer with `Persistent=true`.
- That a stopped service's own image and named volume are never removed. Forgejo's data volume holds the forge.
- Whether the runner's job images are covered here or by the runner's own cleanup.
