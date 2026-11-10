# HO133 — A Host Carries Single Repositories Of A Project

```json
{
  "$schema": "issue-1.json",
  "id": "HO133",
  "title": "A Host Carries Single Repositories Of A Project",
  "state": "Review",
  "size": "M",
  "priority": "Medium",
  "rank": 15,
  "blockedBy": [],
  "covers": "Single repositories of a project carried: the follow takes only those the host's card names, one taken off the forge with its read key at the central forge given the token, status per repository."
}
```

**Why this size.** the follow's taking narrowed to the repositories the host's card names, one repository taken off the
host's forge on its own with its read key, and the project's status per repository; unit tests and the Molecule
scenario's follow act.

**What must be true.** Where the organization's signed state says a host carries only some repositories of a project,
the host's follow migrates those alone, and a repository left out later is taken off the host's forge. Taking one off
deletes its read-only deploy key at the central forge when a central token is at hand, and otherwise names it for its
owner to remove. A project carried whole stays as today. The organization's files and `porelo org host carry` with
single repositories are porelo's part; choosing them in the window and taking one off there is the interface's part.

## Plan

Read in `roles/porelo/files/porelo-host-person` (`follow_take_named_repositories`, `project_status`, the applied state's
`projects`) and `roles/forge/files/porelo-host-project` (`migrate`, `remove`, `left_at_central`).

- **The applied state names the repositories.** A carried project in the state `porelo org` answers gains its host's
  repository names, or none for the whole project. The host checks the field like the rest of the state and refuses
  a name its project file does not list.
- **The follow takes only those:** `follow_take_named_repositories` skips every repository not named, so it neither
  migrates it nor adds a deploy key for it. The project's own repository stays taken, since the project's file lives
  there.
- **A repository left out is taken off:** a new `porelo-host-project` verb removes one repository from the host's forge
  and its read key's private half, after the same checks `remove` makes for the whole project: no unpushed work held
  by a person's branch, the arrivals read. A repository with work not yet at the central forge is held, as a project
  is, and the status says why.
- **Its deploy key at the central forge:** with the token of an `org refresh`, the key of the recorded id is deleted
  (DELETE on `/repos/<owner>/<repo>/keys/<id>`), believed by its absence after. Without a token, the key is named with
  its title and the address where its owner removes it, as a project's removal names them today. The same deletion
  serves [HO114](README.md#ho114) for a whole project later.
- **Status per repository:** `org status` names each repository of a carried project as taken, waiting, held or taken
  off.
- **Red first:** a unit test of the follow with a state naming one of two repositories migrates the other today; one
  of taking off finds no verb.
- **Molecule:** the follow act carries the stand-in project with one of its two repositories, then the other, then
  takes the first off. It checks the forge's repositories and the stand-in central's deploy keys after each step.

## Acceptance

- A host whose card names one repository of a project migrates that one and adds one deploy key; the project carried
  whole migrates all, as today.
- A repository taken off the card leaves the host's forge, and its deploy key leaves the central forge given the token,
  or is named for removal without it.
- Unit tests seen red first; the Molecule scenario green with the new follow steps.

## Answered by the operator

- **A repository with unpushed work on the host** when taken off the card is held until the work reaches the central
  forge, as a project is today (operator, 2026-11-06).

## Done

- **The state's field:** a project in the organization's state may carry `repositories`, a list of the project file's
  repository names, the form agreed with porelo's own part; absent, null or empty carries the project whole, as
  porelo writes it. A list
  that does not read refuses that project alone.
- **The follow:** `follow_take_named_repositories` takes only the named ones and the project's own. One taken before
  and named no longer is taken off; a name the file does not list stands in the project's `why`.
- **Taking off:** `porelo-host-project take-off <project>` with `{"repository", "token"}` on standard input checks the
  repository's refs against its central repository with its read key, as `remove` does, deletes it from the host's
  forge, deletes its deploy key at the central forge with the token, believed by a GET answering 404 after, or names it
  in `left_at_central` without one, then its read key and its manifest row. Work not yet at the central forge refuses
  with 65 and leaves everything; the follow says the row `held` and tries again at each follow (as the operator
  answered).
- **Status:** `org status` says `not-carried` or `held` per repository; `not-carried` gives the project no `why`.
- **Unit tests,** each seen red first: four of the verb (taken off with both keys, no token naming the key, unpushed
  work held, a key still listed after its deletion keeping the read key) and ten of the follow (one named taken
  alone, taken off with and without token, held and tried again, a name the file lacks, five malformed lists).
- **Not done as planned:** the Molecule scenario has no central forge, so its follow act cannot migrate or take off a
  repository with a deploy key. It holds the verb to its form on the real host (a malformed token refused with 64,
  an absent repository answered taken off, the project's own repository kept). The whole flow belongs to the next
  rehearsal on a VM with a central forge.
- **Not done:** a deploy key named without a token is said once, in the follow that took the repository off; the
  manifest row goes with the repository, so no later follow names it again.
- **Checked against porelo's part:** Core's local commit 4d4ce6e3 (work-b479-core) writes a host's repositories per
  project, an empty list for a project carried whole; the host reads an empty list so. Its `org fetch` state does not
  yet carry the field on each project, which porelo's part adds; until then every project is carried whole, as today.
- **Push configurations:** a follow that took a repository off writes the members' push configurations again at once,
  token or not. The task gate was not checked: a task on a repository no longer carried is refused at its start by the
  project file, as before.
- **Changed after the reading (agy, gemini-4-argon-high):** the project's own repository is known by its name on the
  forge, however a row spells its address, and a repository another named row carries is never taken off. `take-off`
  deletes the central key before the host's copy, so whatever fails after the work was checked leaves the repository
  held on the host for the next follow. It refuses Forgejo's answer for a renamed repository, sends a token to the
  organization's forge alone (the check `migrate` makes), and takes the repository's arrivals along. A new forge
  organization clears what the card named. Each of the seven new unit tests was red on the first cut.
