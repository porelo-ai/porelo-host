# HO92 — The Forge's Loopback Port Narrowed To Persons

**Status:** Idea.

**What must be true.** Only the persons and the forge account reach the forge's gate on `127.0.0.1:<git_port>`, as
only they reach `git.sock`: an nftables `output` rule by `meta skuid` on that port, for a set of uids the person helper
keeps, refuses every other account and daemon on the host before its first byte.
