# HO102 — A Person's Projects Named On The Host

**Status:** Review.
**Size:** S - one more file in the follow's publication and its tests; Porelo's reading is its own.

**What must be true.** In a person's host account, `porelo project list` shows every project the host carries for that
person, also before their first start there. Today the account knows no name until then, and the projects' directory
cannot be listed, by design, so that no account learns the names of projects it is not in.

**Plan.** Each follow also publishes one file per person, naming that person's projects: root's, with a read ACL for
that person's account alone, replaced whole like a project's file and gone when the person's last membership is. Porelo
reads it and opens each project's file by name. A test holds that one person cannot read another's file.
