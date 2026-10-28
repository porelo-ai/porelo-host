# HO50 — Down Gives Back When Only A Transport Could Not Clear

**Status:** Estimated.
**Size:** S - one task of the porelo role's `down` reading `vault clear --json`, its end line, one Molecule check.
**Blocked by:** porelo [B318](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b318).

**What must be true.** `down` on a host whose vault a transport could not clear, and nothing else kept, clears the
vault anyway and gives the server back, in a step whose name says so. Any other reason `vault clear` keeps the vault
still stops `down`.

## Why

In 6i's give-back (2026-10-28) `down` stopped at *Clear the vault*. The host had been dismissed from the room and the
laptop's homeserver taken off the VPN, as the guide orders it, so the matrix transport's `clear` could not reach the
homeserver. `vault clear` refused, and the server stayed rented until the account's vault was cleared by hand with
`--force`. porelo-message-matrix lets a revoked token count as cleared. An unreachable homeserver stays a refusal,
since the transport cannot tell a homeserver gone from one briefly away. On a host about to be given back, the vault
goes with its disk either way.

## Plan

- `roles/porelo/tasks/down.yml`: *Clear the vault* runs `porelo vault clear --yes --json`
  ([B318](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b318)). Where it refuses with `kept`
  `transports`, a step of its own, *Clear the vault although a transport could not clear what it keeps*, runs it again
  with `--force`, and fails only where the vault itself was not removed.
- Naming each transport's words in `down`'s last line waits: the lines callback writes a message on a failed line
  only.
- **Red first:** Molecule, a stand-in matrix transport in the account's own directory whose `clear` answers 75.
  Today `down` stops at the vault. With this it ends green, through that step.

## Acceptance

- Molecule: the check above, red, then green.
- The next rental's give-back runs after M5.3 with no hand step.
