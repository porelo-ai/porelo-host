# HO91 — SSH's Edges Left From Its Readings

**Status:** Idea.

**What must be true.** The host's SSH holds at the edges its readings left open: the KRL is validated before sshd
reads it, a root key with an options prefix is refused or kept with its options as given, and a lock is ordered against
a sync that runs at the same time, so neither undoes the other.
