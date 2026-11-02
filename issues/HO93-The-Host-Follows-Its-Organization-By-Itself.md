# HO93 — The Host Follows Its Organization By Itself

**Status:** Backlog.
**Size:** L - root's timer, the adapter's call and its verification, the apply step replacing today's brought state and
per-project sync, Molecule; it builds against Porelo's organization contract.

**What must be true.** A host keeps its persons, its projects and their members as its organization says, without
anybody bringing it anything: every five minutes, and at once when the host admin asks for it, root fetches the
current signed state through the installed organization adapter, checked against the host's pin and the last state it
took, and applies it.

## Plan

- The contract it builds against: the adapter answers, for a host, its pin and the last state taken, the new state
  with its persons (login, card key, revocation) and the projects the host carries with their members and roles, or a
  refusal with its reason; nothing older than the last state is ever answered.
- `roles/porelo/files/porelo-host-person`: a verb `follow` replaces `registry --stdin` and the per-project `sync` as
  the way state arrives. It runs the adapter as today's verify runs Porelo, as a throwaway user with no network but
  the forge's, reads its JSON answer, refuses anything not signed for the pinned host, and then admits, locks and sets
  memberships through today's code paths. `registry status` answers the state last followed.
- A systemd timer and service of root's, `porelo-host-follow`, every five minutes, `Persistent=true`; a refusal fails
  the unit loudly and changes nothing.
- A root verb the host admin reaches over SSH for *Refresh*, answering what changed.
- Red first: a state older than the last one is refused; a revoked person is locked on the next follow; a project the
  host no longer carries locks its members who hold no other membership.

## Acceptance

- Molecule: a changed organization reaches the host within one timer run and at once on refresh; a played-back older
  state is refused and logged; a revocation locks the person.

## To be checked

- The adapter's call on the host: its executable, arguments and the account it needs.
- Where `up` takes the organization's address from: Porelo's own setting on the host.
