# HO77 — Each Job In A Network Of Its Own

**Status:** Idea (operator, 2026-10-30).
**Size:** -

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** Concurrent jobs on a host cannot reach one another's network, and no host login reaches Forgejo
over TCP.

- Today ([HO69](README.md#ho69)) every job joins the runner's network namespace, where one proxy forwards to the
  runner's socket of the forge's gate, so jobs share one loopback.
- The job images are third-party, so a proxy cannot be built into them: each job would start its own proxy from a
  mounted socket as its first step, or the runner would start each job in a pod of its own.

- Jobs get a read-only `/etc/hosts` of root's. Steps run as `uses: docker://…` do not get the runner's container
  options, so they still see the proxy's own `/etc/hosts`, and every container shares the proxy's `/etc/resolv.conf`.
  A job could rewrite either for later jobs until the proxy restarts.

## Open questions

- A first workflow step every project carries, or a runner that starts jobs in pods; and the Actions cache's own path.
