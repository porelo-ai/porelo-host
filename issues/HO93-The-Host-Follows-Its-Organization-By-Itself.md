# HO93 — The Host Follows Its Organization By Itself

**Status:** Backlog.
**Size:** L - root's timer, the adapter's call and its verification, the apply step replacing today's brought state and
per-project sync, Molecule; it builds against Porelo's organization contract.

**What must be true.** A host keeps its persons, its projects and their members as its organization says, without
anybody bringing it anything: every five minutes, and at once when the host admin asks for it, root fetches the
current signed state through the installed organization adapter, checked against the host's pin and the last state it
took, and applies it.

## Plan

- The contract it builds against: the adapter answers, for a host, its pin and the last state taken, the new state with
  its persons (login, card key, revocation) and the projects the host carries with their members and roles, or a refusal
  with its reason; nothing older than the last state is ever answered.
- `roles/porelo/files/porelo-host-person`: a verb `follow` replaces `registry --stdin` and the per-project `sync` as the
  way state arrives. It runs the adapter as today's verify runs Porelo, as a throwaway user with no network but the
  forge's, reads its JSON answer, refuses anything not signed for the pinned host, and then admits, locks and sets
  memberships through today's code paths. `registry status` answers the state last followed.
- The organization's repository is read with a read-only deploy key made on the host at `up`, root's alone, its public
  half added with the host admin's token sent once; the follow's unit alone reaches the central forge with it.
- From `signingKeys` in the state taken, a Porelo command builds each project's allowed signers and certifiers; the
  follow writes them where `commit verify` and the task certificates' check read them, in place of today's
  `push_signers` from `project.signers`.
- A person's Porelo fetches the project repository in their own account from the configured forge. Where the host runs a
  forge, that is the host's, with the person's local forge token; there the repository has root as its only writer, kept
  in step from the central forge with its deploy key, fast-forward only, a divergence named instead of forced. Where the
  host runs none, it is the central forge, with the person's own central read token, kept in their vault on the host and
  lent by `porelo vault credential`; a shut vault means no fetch. Each project's `signingKeys` rows are published by
  root, readable by its members alone. Nothing of root's credentials is readable by a person.
- A systemd timer and service of root's, `porelo-host-follow`, every five minutes, `Persistent=true`; a refusal fails
  the unit loudly and changes nothing.
- A root verb the host admin reaches over SSH for *Refresh*, answering what changed.
- A person who is a member of no project the host carries any more is locked on that follow. Seven days later the
  follow purges their account by itself: the Linux account with whatever it holds unpushed, their forge users and
  tokens, and their Matrix accounts expelled where the gate runs. The record keeps the day of the lock; a person taken
  back into a project within the seven days is unlocked and finds the account as they left it.
- Red first: a state older than the last one is refused; a revoked person is locked on the next follow; a project the
  host no longer carries locks its members who hold no other membership. Such a person is purged on the first follow
  seven days after the lock and not before; taken back within them, they are unlocked with their account untouched.

## Acceptance

- Molecule: a changed organization reaches the host within one timer run and at once on refresh; a played-back older
  state is refused and logged; a revocation locks the person.

## To be checked

- The adapter's call on the host: its executable, arguments and the account it needs.
- Where `up` takes the organization's address from: Porelo's own setting on the host.
