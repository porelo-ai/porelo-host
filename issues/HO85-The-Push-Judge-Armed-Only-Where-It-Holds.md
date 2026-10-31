# HO85 — The Push Judge Armed Only Where It Holds

**Status:** Idea; blocked by [HO76](README.md#ho76).

**What must be true.** A repository is recorded as armed only when its hook link names the mounted hook, which is
there and executable, and no link stands on its way; a forge without the repositories' directory stops the arming. A
project's removal takes its arrivals along. Reading arrivals holds the lock the writers hold, and every record and its
directory are checked root's and private before a read. A verdict is recorded only with a valid arrival time, commit
and signer fingerprint, and the KRL is read only when it is root's regular file. The push judge's socket restarts
before Forgejo, and a push mixing a deletion with an update is judged. The texts name the socket as the forge
account's and the mount as the directory's.
