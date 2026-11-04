# HO123 — A Socket Forward Reaches Past The Agent Rule

**Status:** Backlog.

**What must be true.** What a person's ssh can do with their agent on a host is written down and meant. `AllowAgentForwarding no`
does not read as more than it is.

## Why

Every account has `AllowAgentForwarding no`, so `ssh -A` gives a session no agent. But `porelo-people` keeps
`AllowStreamLocalForwarding all`, for the return socket and the daemon's, and OpenSSH has no per-path allowlist. So by reading,
`ssh -R <socket on the host>:$SSH_AUTH_SOCK` puts the agent on the host all the same, for a person who asks for it. It was not run.
While it stands, root on that host can have anything signed with the key: a rented machine's root is not the person.

`doc/ssh.md` says agent forwarding is disabled and that sockets are guarded by modes alone, and does not join the two. The question
came up when a task on a host wanted a certificate from a card at the person's desk.

## Decided

`doc/ssh.md` says so and nothing is restricted: the scope protects from agents and outsiders, not from a person's own rights, and a person
with a shell can run such a forward without any sshd rule. A task's certificate must not need it, which is not this repository's.

## Acceptance

- `doc/ssh.md` says what the rule stops and what it does not, and what a person risks.
