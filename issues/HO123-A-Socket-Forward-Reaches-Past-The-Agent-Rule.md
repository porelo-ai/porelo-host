# HO123 — A Socket Forward Reaches Past The Agent Rule

**Status:** Idea.

**What must be true.** What a person's ssh can do with their agent on a host is written down and meant. `AllowAgentForwarding no`
does not read as more than it is.

## Why

Every account has `AllowAgentForwarding no`, so `ssh -A` gives a session no agent. But `porelo-people` keeps
`AllowStreamLocalForwarding all`, for the return socket and the daemon's, and OpenSSH has no per-path allowlist. So by reading,
`ssh -R <socket on the host>:$SSH_AUTH_SOCK` puts the agent on the host all the same, for a person who asks for it. It was not run.
While it stands, root on that host can have anything signed with the key: a rented machine's root is not the person.

`doc/ssh.md` says agent forwarding is disabled and that sockets are guarded by modes alone, and does not join the two. The question
came up when a task on a host wanted a certificate from a card at the person's desk.

## To decide

- **Say so and leave it:** the person's own choice on their own socket, and a shell can reach it anyway. `doc/ssh.md` says what is and
  is not stopped. Likely, as a rule cannot stop a person with a shell from running a forwarder of their own.
- **Forward named sockets only,** which needs a command in place of the shell, or a change OpenSSH does not offer. Costly, and
  a person's login shell stays.

Whichever: a task's certificate must not need it. That is not this repository's.

## Acceptance

- `doc/ssh.md` says what the rule stops and what it does not, and what a person risks; if the second is chosen, a test holds it.
