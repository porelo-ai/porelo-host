# HO103 — A Project Put On Again After Off

**Status:** Accepted.

**What must be true.** A project put on a host, taken off and put on again is taken. Today taking it off leaves the
host's deploy key at the central forge, and the new key has the same title, so Forgejo answers 422 and the helper
refuses, seen as `the central forge refused the deploy-key request (HTTP 422)`. GitHub's answer to the same title is not
measured. So `off` must also say truthfully what stays: nothing on the host, a deploy key at the central forge.

**Plan.** Read the removal's reach first: the host's credential for the central forge may not be allowed to delete a
key. Either the removal deletes its own key, or the migration replaces a key of its own title. A test on a forge holds
the round.

**The same for the organization.** A host's read key on the organization's repository is taken off by nobody: a host
set up anew or given up leaves its old key able to read until the repository's owner removes it.
