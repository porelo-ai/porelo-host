# HO124 — A Login Closed At Once On A Host

**Status:** Backlog.

**What must be true.** A host's own ssh does not shut out a person's interface for what the interface itself did, or if it does, the
person can read why and what to do.

## Why

The first real *Take Porelo off this machine…* on a rented host ended at its first read, root's `org status`, with "Connection
closed by <address> port 22", in 0 s; the machine's row fell back to "not connected yet". The server was deleted, so the cause
stays unknown. Nothing in the collection closes a login: the key lookup and the KRL refuse with "Permission denied", and no role sets
`PerSourcePenalties` or `MaxStartups` or limits a rate in the firewall.

## Hypothesis, by reading and from memory

**sshd's own per-source penalty, by OpenSSH's default since 9.8,** from memory: a source that has run up failed logins and connections
without one, each to a few seconds, is dropped before the banner for that time, and the client sees exactly this line. A window does
that: connections asked again every minute, failed logins while root was still closed, host key fetches. Next most likely: `MaxStartups`,
or the operator's deletion having begun.

## Plan

- **Reproduce on the test VM:** a burst of failed logins and bare connections, then the helper's read, and read `journalctl -u ssh`
  for "penalty". It shows whether this happens and how long it lasts.
- **If so:** a window tells this case from the others, by its words and a wait, its part. The collection says it in `doc/ssh.md`; lowering
  the penalty for a person's own address is not offered, as the address is not known, and the default protects a public port.

## Acceptance

- The reproduction's result here, with OpenSSH's version: the cause shown, or this one ruled out.
- `doc/ssh.md` names what a person meets and what to do.
