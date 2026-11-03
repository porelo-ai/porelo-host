# HO101 — One Forge Over SSH And HTTPS On A Port

**Status:** Idea.

**What must be true.** An organization at `ssh://git@host:2222/...` and a project at `https://host:3443/...` on the same
forge count as one forge. Today the helper drops the port for ssh and keeps it for https, so the two origins differ and
the migration refuses, exit 65. An address cannot tell by itself which ports belong together, so this needs a setting
naming the forge's https origin. GitHub's addresses carry no port and do not meet it.
