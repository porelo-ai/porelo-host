# HO70 — The Host's State Taken From The Registry

**Status:** Accepted (operator, 2026-10-30, with the project's one-click joining).
**Size:** M - the registry's intake in root's sync and admit and register checked against it, with unit tests and a VM
run; measured M median 63 min, from three M builds (47, 63, 75).
**Blocked by:** Porelo's registry verify.

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** The host takes which project admins and projects it has from the signed registry state the host
admin's Porelo brings it, never from the central forge itself.

- The host admin's Porelo uploads a bundle of the registry repository through the tunnel into their account's setup
  directory, as a project's access bundle goes today. Root's sync verifies it in its isolated unit with Porelo's
  registry verify and applies the answer; the host parses no signature itself.
- The anchor: at setup the host pins the key that signed its host card. Porelo's verify accepts `hosts/<host>/…` only
  when signed by that key or its named successor, as the project's decision and `owners.yml` rule; registry owners'
  rotation and backup keys are Porelo's to check.
- A project admin registers a project only where `hosts/<host>/access.yml` names them for it. A project dropped there is
  refused at its next sync and named in the sync's answer for the host admin; the host never removes it on its own.
- A sync that meets a bad entry names it and keeps applying the rest, so a refused login never holds up a lock or a
  revocation in the same run.

## Tests

- a bundle signed by another key is refused whole; a dropped project is named and kept; a re-admitted purged login is
  refused alone while a lock in the same bundle applies.
