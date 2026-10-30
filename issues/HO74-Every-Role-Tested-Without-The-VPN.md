# HO74 — Every Role Tested Without The VPN

**Status:** Accepted (operator, 2026-10-30, with the project's one-click joining).
**Size:** M - Molecule's scenario and the host's guide rewritten for SSH alone; measured M median 63 min, from three M
builds (47, 63, 75).
**Blocked by:** [HO63](README.md#ho63), [HO68](README.md#ho68), [HO69](README.md#ho69), [HO70](README.md#ho70),
[HO71](README.md#ho71), [HO72](README.md#ho72), [HO73](README.md#ho73), [HO75](README.md#ho75), [HO76](README.md#ho76).

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** Molecule shows every role of the host over SSH alone, and the guide's checks pass on a rented
host without hand patches.

- The test peer reaches the forge, the homeserver and the daemon only through an SSH tunnel with a person's key, and
  nothing else on the host from outside.
- `doc/guides/6-host.md` and its scripts without the VPN, the CA and the stops that went, tried once on a rented host.
  The preparation checks that the host runs the porelo-host collection and helpers of the commit under test, so what
  [HO67](README.md#ho67) asked of a rented host stays.
