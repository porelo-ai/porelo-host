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

## Notes

- Forwarding differs from [HO68](README.md#ho68), accepted for the 6m test (Coordinator, 2026-10-30, for the
  operator to see): `porelo-people` gets `AllowTcpForwarding yes` and `PermitListen none` besides socket forwarding.
  OpenSSH 10.2 opens no Unix-socket forward while TCP forwarding is off, and `PermitOpen none` refuses socket paths
  too, as a debug `sshd` on the test VM showed. Residual risk: a person's local TCP forward reaches every address the
  host reaches, such as the homeserver's empty loopback port, other hosts on its networks and the internet, which is
  what their login shell reaches already; remote TCP listeners stay refused. The narrower way is
  [HO78](README.md#ho78).
