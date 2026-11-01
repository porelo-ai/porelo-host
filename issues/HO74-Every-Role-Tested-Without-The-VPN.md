# HO74 — Every Role Tested Without The VPN

**Status:** Implementing; its persons' lock and purge wait for the published Matrix transport whose `expel`
reaches the homeserver through the gate.
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

- Forwarding differs from [HO68](README.md#ho68), accepted for the 6m test: `porelo-people` gets `AllowTcpForwarding yes` and `PermitListen none` besides socket forwarding.
  OpenSSH 10.2 opens no Unix-socket forward while TCP forwarding is off, and `PermitOpen none` refuses socket paths
  too, as a debug `sshd` on the test VM showed. Residual risk: a person's local TCP forward reaches every address the
  host reaches, such as the homeserver's empty loopback port, other hosts on its networks and the internet, which is
  what their login shell reaches already; remote TCP listeners stay refused. The narrower way is
  [HO78](README.md#ho78).
- Skipped until this rewrite, to keep the Build green: verify's includes of
  `tasks/reboot.yml`, `people.yml`, `projects.yml` (with `bring.yml`), `push.yml` and `two_projects.yml` carry the
  tag `notest`, and the operator admission in `forge_person.yml` is off. Each still builds the VPN host's input
  (WireGuard keys, `10.73.7.0/24`, the forge CA, laptop lines on `add`'s stdin). This rewrite takes the tags off.
  `push.yml` also waits for [HO80](README.md#ho80), which changes the push.

## Part 2 also takes

Molecule's own checks and its registry fixture, read after part 1, are made exact with part 2:

- `people.yml` checks `authorized_keys` whole, not by its last line, so an extra earlier key fails.
- The refusals after admission compare the accounts and the people records before and after.
- The forge logins are compared as the exact set, and the person's token is checked by signing in with it, not by its
  shape.
- The locked record excludes a trailing `lock=pending`.
- The leak scan covers `forge-token`'s stderr, the admin token minted for the check and the fixture's private keys.
- `files/registry-bundle.sh` runs under `umask 077` with an isolated git configuration, takes a relative `DIR`, keeps
  `registry verify`'s temporary files in its own directory, quotes `${PROJECTS}` and its YAML scalars.
- `/root/verify-registry` and the persons are removed after a failure too, and the SSH master has an exit trap.
