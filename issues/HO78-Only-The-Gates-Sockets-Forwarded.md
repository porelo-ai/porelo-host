# HO78 — Only The Gates' Sockets Forwarded

**Status:** Idea (Agent Machines, 2026-10-30, on the Coordinator's word).
**Size:** -

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** A person's SSH connection forwards only to the gates' sockets and to their own return socket,
and to no TCP address.

- Today ([HO74](README.md#ho74)) `porelo-people` has `AllowTcpForwarding yes` with `PermitListen none`: OpenSSH 10.2
  forwards no Unix socket while TCP forwarding is off, and `PermitOpen none` refuses socket paths too, with no
  per-path allow list. A local TCP forward reaches what the person's shell on the host reaches anyway.

## Open questions

- A later OpenSSH with a per-path allow list for Unix sockets, or a forced command or proxy that opens only the
  gates' sockets, with the interface's and Element's tunnels unchanged for the person.
