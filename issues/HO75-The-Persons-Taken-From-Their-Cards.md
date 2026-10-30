# HO75 — The Persons Taken From Their Cards

**Status:** Accepted (operator, 2026-10-30, with the project's one-click joining).
**Size:** M - laptops out of `porelo-host-person`, persons, keys, signers and per-project locks from the verify answers,
with unit tests and a VM run; measured M median 63 min, from three M builds (47, 63, 75).
**Blocked by:** [HO70](README.md#ho70); Porelo's verify answering persons by key.

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** A person on the host is a login with the one key of their card, whatever machine they sit at.
Their access per project follows the project's access file, their access to the host follows its registry state.

- The persons come from the verify answers: login, key, expiry, revocation, and per project their role and whether that
  project locks them. `porelo-people` holds exactly the admitted logins not locked by the host.
- A project admin's lock in the access file takes the person out of that project's forge teams and, through the Matrix
  transport's `members`, its rooms; their account and other projects stay. Let back in undoes it. The host admin's lock
  and a revoked or stolen key lock the person's host account at once ([HO68](README.md#ho68) ends the sessions); the
  vault's reset after a lost key is Porelo's.
- Git's allowed signers on the host's forge come from the admitted persons' keys: the project admins' as
  `cert-authority` limited to the tasks' namespaces and principals, a replaced key kept with `valid-before` for history
  only. Removing a person drops their line.
- A purged login is kept on a host list and refused if admitted again.
- Goes: laptops, their `l<n>` names, SSH keys and VPN addresses per laptop in `porelo-host-person`, the host CA's values
  in the access file's `host:` block, the project's own signing key as a signer.

## Tests

- a project lock removes only that project's teams and rooms; a host lock or a revoked key ends the account's sessions
  and keys at once; signers follow the access file.
