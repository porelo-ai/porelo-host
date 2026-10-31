# HO84 — The Person's Daemon By A Fixed Name

**Status:** Review.
**Size:** S - one link and one boot rule line in one class, but the two names are a contract the person's tunnel
builds on.

**What must be true.** A person's tunnel reaches their daemon and binds its return socket by names that follow from
the login alone: `/run/porelo-host/people/<login>/porelod.sock` and `/run/porelo-host/people/<login>/return.sock`.

## Plan

- `Host.admit_runtime` in `roles/porelo/files/porelo-host-person` makes the link `porelod.sock` in the person's 0700
  runtime directory to `/run/user/<uid>/porelo/porelod.sock`, porelod's own socket, and adds an `L` line for it to
  the person's tmpfiles rule, so a boot or `restore-runtime` makes it again. A person's own entry at that name stays,
  also one made between root's look and its link. Adding a recorded person again restores it. Lock and purge remove
  it with the directory. The link dangles while the account's porelod is not running; a forward through it then
  fails.
- `return.sock` needs nothing on the host: sshd binds it in the person's directory with `StreamLocalBindUnlink yes`.
- Red first: `tests/unit/roles/test_host_ssh_access.py` and `tests/unit/roles/test_porelo_host_person.py` expect the
  link to the account's own uid, the rule's second line, a person's file or dangling link left alone, and a raced
  entry kept. `doc/ssh.md`, `roles/porelo/README.md` and `CHANGELOG.md` name both sockets.

## Acceptance

- [ ] after admission and after a restore, `porelod.sock` links to the account's daemon socket and the rule holds it;
- [ ] a person's own file at that name is not replaced.
