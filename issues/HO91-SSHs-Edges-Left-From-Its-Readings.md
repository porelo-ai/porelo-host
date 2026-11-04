# HO91 — SSH's Edges Left From Its Readings

**Status:** Idea.

**What must be true.** The host's SSH holds at the edges its readings left open: the KRL is validated before sshd
reads it, a root key with an options prefix is refused or kept with its options as given, and a lock is ordered against
a follow that runs at the same time, so neither undoes the other.

Read in today's code, not run: `write_krl` checks only the file's header before replacing it. `roles/base/tasks/ssh.yml`
lets a key with a prefix pass and keeps its first two fields as the seed. A lock and a follow both take `forge.conf`'s
exclusive lock, which no test here holds yet.
