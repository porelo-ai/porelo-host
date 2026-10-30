# HO75 — The Persons Taken From Their Cards

**Status:** Implementing.
**Size:** M - laptops out of `porelo-host-person`, persons, keys, signers and per-project locks from the verify answers,
with unit tests and a VM run; measured M median 63 min, from three M builds (47, 63, 75).
**Blocked by:** [HO68](README.md#ho68), [HO70](README.md#ho70), [HO71](README.md#ho71); Porelo's verify answering
persons by key.

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** A person on the host is a login with the one key of their card, whatever machine they sit at.
Their access per project follows the project's access file, their access to the host follows its registry state.

- The persons come from the verify answers: login, key, expiry, revocation, and per project their role and whether that
  project locks them. `porelo-people` holds exactly the admitted logins not locked by the host.
- A project admin's lock, or a removal from one project while others stay: the person, their agent forge user and their
  task accounts leave that project's forge teams and, through the Matrix transport's `members`, its rooms; their signer
  lines leave that project. The account, its sessions, tokens and other projects stay; Let back in undoes it.
- A host admin's lock, the person's current key in the KRL, or the removal of the last membership locks the account,
  and [HO68](README.md#ho68) and [HO71](README.md#ho71) end its sessions and tokens. The vault's reset after a lost key
  is Porelo's.
- Each project's allowed signers on the host's forge are its own unlocked persons: each with a plain-key line for their
  own commits and a `cert-authority` line limited to the tasks' namespaces and principals for the certificates of the
  tasks they start; a replaced key kept with `valid-before` for history only. A person of one project is never a signer
  of another.
- A purged login is kept on a host list and refused if admitted again.
- Goes: laptops, their `l<n>` names, SSH keys and VPN addresses per laptop in `porelo-host-person`, the host CA's values
  in the access file's `host:` block, the project's own signing key as a signer.

## Tests

- a project lock removes only that project's teams, rooms and signer lines; a host lock or the current key in the KRL
  ends the account's sessions and tokens, an older key in the KRL does not; signers are per project.
