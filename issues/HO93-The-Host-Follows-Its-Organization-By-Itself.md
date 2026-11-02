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
- `up` takes from the machine file the interface writes: the person's `organization.yml`, handed unread; the central
  forge's SSH host key lines as the person's machine trusts them; and the pin, one `login key` line per host admin of
  this host as `porelo org` names them, backup keys included. It writes them root-only under
  `/etc/porelo-host/organization/`; `org pin` goes. It makes the host's read-only deploy key for the organization's
  repository and answers its public half in `host.json`. The host admin's central token comes once, on standard input of
  `org refresh` right after `up`; the host adds the deploy key with it and keeps none. Until then `org status` answers
  `"organization": "waiting-for-token"` and the host follows nothing. The follow's unit alone reaches the central forge
  with that key.
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
- *Refresh* is `porelo-host-person org refresh`, root's, reached by the host admin over SSH: it follows at once and
  answers as `org status` does. It takes the host admin's central token on standard input only while a project waits for
  it (HO94), takes an empty input otherwise, and refuses a token nobody waits for, so none lies unused.
- `org status` answers, besides the host and its persons, `projects`: each with `state` (`carried`, `putting-on`,
  `waiting-for-token`, `held`, `gone`), `why` (for `held`, the repositories with unpushed commits) and `since`; a locked
  person carries `purge_on`, the day the account is deleted.
- The fetch is `porelo org fetch --host --settings --ssh-key --known-hosts --pin --since`: the organization repository's
  deploy key and the central forge's host key pinned at `up`, both root's; the pin is the set of host admin keys last
  taken, written back only once an answer is taken.
- A person who is a member of no project the host carries any more is locked on that follow. Seven days later the follow
  purges their account by itself: the Linux account with whatever it holds unpushed, their forge users and tokens, and
  their Matrix accounts expelled where the gate runs. The record keeps the day of the lock; a person taken back into a
  project within the seven days is unlocked and finds the account as they left it.
- Red first: a state older than the last one is refused; a token given to *Refresh* with no project waiting is refused;
  a revoked person is locked on the next follow; a project the host no longer carries locks its members who hold no
  other membership. Such a person is purged on the first follow seven days after the lock and not before; taken back
  within them, they are unlocked with their account untouched.

## Acceptance

- Molecule: a changed organization reaches the host within one timer run and at once on refresh; a played-back older
  state is refused and logged; a revocation locks the person.

## To be checked

- The adapter's call on the host: its executable, arguments and the account it needs.
- Where `up` takes the organization's address from: Porelo's own setting on the host.
