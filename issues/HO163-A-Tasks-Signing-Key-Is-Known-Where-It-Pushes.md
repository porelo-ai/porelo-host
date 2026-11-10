# HO163 — A Task's Signing Key Is Known Where It Pushes

```json
{
  "$schema": "issue-1.json",
  "id": "HO163",
  "title": "A Task's Signing Key Is Known Where It Pushes",
  "state": "Backlog",
  "size": "S",
  "priority": "Medium",
  "rank": 4,
  "blockedBy": [],
  "covers": "A task's signing key is registered with the forge account that receives its push, so its commits verify on the host's forge; what the central forge can take is measured first."
}
```

**Why this size.** a measurement on both forges and its record here; registering a task's key at its start is the
host program's and is filed in porelo for Agent Core after the measurement.

**What must be true.** A task's signed commits show as verified on the host's forge, since the key a task signs with is
registered with the forge account that receives its push, and the same commits brought to the central forge do not
read as signed by an unknown key there.

## Plan

- **Measure first.** On a host with a forge: register a task's public signing key, and its certificate, with the
  forge account that receives the push, and read what Forgejo's API says of the task's commit. At the central forge
  (GitHub, porelo-ai-test), read what it takes as a signing key: a plain SSH key does, a certificate perhaps not.
- **Write it down** in this issue, then file the host program's part (the key registered when a task starts, taken
  off when it ends) in porelo for Agent Core; this issue then waits on it.

## Acceptance

- On the host's forge, a task's commit shows a verified signature of the task's account; a commit signed by any other
  key does not.
- What the central forge can be told of a task's key, and what it cannot (a certified key the central forge does not
  take), is measured and written down before anything is built for it.

## Measured

On the foo-org host (main at 888d1f0), 2026-11-09: a commit signed in task `pi` with its certified key
(`ssh-ed25519-cert-v01`, principal `task:foo-project:pi`) passed the push judge and was forwarded by `porelo gate
approve`; Forgejo's API reads it as `verified: false`, `gpg.error.no_gpg_keys_found`. A person's own signed commit
reads the same. The forge account that receives the push holds no key of the task. GitHub was not measured: the
test identity's token may not read checks or open pull requests there.
