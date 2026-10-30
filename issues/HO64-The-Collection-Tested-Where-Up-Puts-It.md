# HO64 — The Collection Tested Where Up Puts It

**Status:** Idea. Waits for the interface to install the collection for every account under `/usr/share/ansible/collections`.

**What must be true.** Molecule installs the collection the way `up` does once the interface installs it there, and
verify shows that a person's own account resolves `porelo.host` from `/usr/share/ansible/collections` at the version
under test. The README names that place.

## Why

Walk 23: `porelo.host.bring` was not found in walkadmin's account, as the collection was only under `/var/tmp`.
Molecule hid the gap: `tasks/bring.yml` installs the tarball into bo's and cy's `~/.ansible/collections` itself, which
no product code does, and the README says to install the tarball without saying where.
