# HO93 — The Host Follows Its Organization By Itself

**Status:** Implementing.
**Replaces:** [HO46](README.md#ho46): the developers kept in step, now with the organization in place of the access file.
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
  `org refresh` right after `up`; `porelo org add-read-key` adds the deploy key with it, since only the adapter reads the
  settings, and the host keeps none. Until then `org status` answers
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
  it ([HO94](README.md#ho94)), takes an empty input otherwise, and refuses a token nobody waits for, so none lies unused.
- Within `org fetch` Porelo also asks the central forge's public key list, anonymously, to judge a member's first card;
  so the follow's unit needs HTTPS out as well as SSH, and no credential for it. A forge with no such list leaves that
  person first-seen, so the commit waits and the host stays at the state it took.
- `org status` answers, besides the host and its persons, `projects`: each with `state` (`carried`, `putting-on`,
  `waiting-for-token`, `held`, `gone`), `why` (for `held`, the repositories with unpushed commits) and `since`; a locked
  person carries `purge_on`, the day the account is deleted. `refused` holds the words of what the last fetch refused:
  a removal of the host and a commit nobody allowed look alike, so the host keeps the state it took and the host admin
  judges.
- The fetch is `porelo org fetch --host --settings --ssh-key --known-hosts --pin --since`: the organization repository's
  deploy key and the central forge's host key pinned at `up`, both root's; the pin is the set of host admin keys last
  taken, written back only once an answer is taken. The fetch's unit keeps Porelo's trust record in a state directory
  of its own, so a follow from the commit taken asks the forge nothing.
- A person who is a member of no project the host carries any more is locked on that follow. Seven days later the follow
  purges their account by itself: the Linux account with whatever it holds unpushed, their forge users and tokens, and
  their Matrix accounts expelled where the gate runs. The record keeps the day of the lock; a person taken back into a
  project within the seven days is unlocked and finds the account as they left it.
- Red first: a state older than the last one is refused; a token given to *Refresh* with no project waiting is refused;
  a revoked person is locked on the next follow; a project the host no longer carries locks its members who hold no
  other membership. Such a person is purged on the first follow seven days after the lock and not before; taken back
  within them, they are unlocked with their account untouched.
  A person still listed in a project, locked there or with a revoked card, is locked and never purged.

## Acceptance

- Molecule: a changed organization reaches the host within one timer run and at once on refresh; a played-back older
  state is refused and logged; a revocation locks the person.

## To be checked

- Molecule on a stand-in for `porelo org fetch`, `org signers` and `org add-read-key`, whose real commands are not built yet.
