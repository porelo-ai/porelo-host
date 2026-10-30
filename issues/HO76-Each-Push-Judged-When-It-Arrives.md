# HO76 — Each Push Judged When It Arrives

**Status:** Accepted (operator, 2026-10-30, with the project's one-click joining).
**Size:** M - a pre-receive check on the host's forge and its record, with unit tests and a VM run; measured M median 63
min, from three M builds (47, 63, 75).
**Blocked by:** [HO75](README.md#ho75); Porelo's commit verify against signers and KRL.

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** The first accepted push of a commit to the host's forge is its arrival: there it is judged
against the signers and the KRL in force, with no `valid-before` key, and the verdict is recorded.

- A pre-receive hook asks Porelo to verify each new commit and task signature against the allowed signers and KRL now in
  force; a commit that fails is refused, naming it.
- Each accepted commit's verdict, with the arrival time and the signing key's fingerprint, is recorded append-only on
  the host, readable by the project's persons.

## Tests

- a commit signed by a revoked key, or by an expired task certificate, is refused; a good one is recorded with its time.
