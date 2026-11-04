# HO60 — Each Repository's Review Set On The Forge

**Status:** Review.
**Size:** L - the signed project file read at each follow, every repository it names taken with one token, the
protection from its value, and Molecule steps on the real forge for both values and a change between them.

**What must be true.** The host takes every repository the signed project file names, and its local forge protects each
repository's `main` according to the value that file gives it under `repositories.<name>.review`, and the project's
own repository's `main` according to `project.review`, with the same meaning:

- **`required`**, also when the key is left out: a pull request is merged only after one approval by a person other
  than its author, and a commit pushed after an approval dismisses it.
- **`optional`**: no approval is needed; the author may merge their own pull request.
- **Either way:** only the forge's teams of owners and developers may merge or approve, never the teams of agents or
  gates; nobody pushes straight to `main`, also not an owner; pull requests are merged by fast-forward only.

## Where the values come from

Only from the project's own `main` at the central forge, as Porelo verified it against the project's signers. At each
follow the helper asks for that `main` with the repository's read key. If the commit or the signers changed, it makes a
bare copy of `main` alone, owned by the forge's account, and an isolated `porelo project verify --repository GIT-DIR --signers FILE --json` reads it
with no network. A file that cannot be read or is refused changes nothing, and the last values hold, and `org status`'s
`why` says so. A value never read, and a repository the file does not name, is `required`.

## Contract with Porelo

The host reads what Porelo's review key in the project file answers:
`project verify` answers `project`, `project_review`, and `repositories.<name>` with `review`, `upstream` and `central`,
a string or `null`. A bad value or a file not signed by a signer exits 65, naming why. `central` is where the host takes
the repository from; `upstream` stays what a task reads, the local forge. The host does not parse the file.

## How the repositories arrive

- In a follow with a token, the project's own repository is taken first, then the file is read from it, then every
  other repository with a `central` is taken with that same token, so no second token is asked for.
- **A repository named later** waits for a token: `state` is `waiting-for-token`, and `why` names it. The others go on.
- **A repository refused**, as on another forge than the organization's, is named in `why`; the next is still taken.
- **A repository without `central`** is not taken; it has a review value only if it stands on the forge by that name.
- **A repository taken out of the file** stays on the host with its work and returns to `required`.

## How a value reaches the forge

Each follow compares every repository's rule with the value in force and sets it where it differs, so a rule changed by
hand comes back, and names each change on standard error, which reaches the journal. A protection that cannot be set fails
the follow naming the repository; the other repositories are still set, and the old rule stays.

## What the code does not keep today

**"Never the teams of agents or gates" holds for the teams' names alone.** Read, not run: the follow puts a person's gate
login `porelo-<login>` into `developers` in every project of that person, and nobody into `gates`, so that login is on the
approval and merge lists. A task's token belongs to that login with `write:repository`, so the token can approve and
merge. What keeps a task from doing so is only that the box never holds the token and the gate offers no route to the
forge's API, not the forge's own rule this issue promises.

## Acceptance

- The unit tests of the above, seen failing without the change.
- Molecule on the real forge: `optional` lets the author merge alone and still takes no direct push; `required` does
  not; a rule changed by hand is set back.

## To be checked

- With Porelo's real `project verify`: that it reads the copy as the forge's account, and that a large history stays
  within the minute a follow gives all files.
- That the forge's `dismiss_stale_approvals` dismisses an approval on a push to the pull request's branch; it takes a
  second person, so Molecule sees the rule's field only.
- Whether a pull request open while the value changes from `optional` to `required` keeps its merge button.
