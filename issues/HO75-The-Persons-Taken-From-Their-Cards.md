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

## Plan

- Replace device intake in `roles/porelo/files/porelo-host-person` with verified card records (`ssh`, `expires`),
  project roles and locks. Keep registry and project verification in their existing isolated units; keep project
  bundle trust anchors separate from commit signers. Reject reserved logins and permanently retain purged logins.
- Reconcile only the affected project's forge teams through the private socket and its Matrix room membership
  through the service-account transport. Retain an applied person roster for retry and host-wide revocation.
  Reuse account, session and token revocation for host locks, current-key revocation and last-membership removal.
  Record failed host locks as locked so project sync cannot restore their access.
- Publish root's project-local allowed signers and private rotation history under `/etc/porelo-host/signers/`.
  Restrict task CA lines to namespace `git` and principals `task:*`; bound historical keys by replacement time and
  the old card expiry. Keep the project helper and teardown guard compatible with the new person records.
- Red first in `tests/unit/roles/test_porelo_host_person_cards.py`: project-local locks and restoration, host locks,
  current versus old KRL keys, signer isolation and history, purge refusal, expiry and removal of device intake.
  Retain account, teardown and registry guards in `test_porelo_host_person.py`, use its Forgejo API fake for all-team
  removal, and migrate the certificate suite's card records. Update the role and local-forge documentation.

## To be checked

- Confirm the Matrix transport's project membership invocation and task signer namespace convention with their
  producers; the host unit tests use fakes for those boundaries.
- Run the pinned container checks, document checks and local VM workflow, and obtain independent review.
