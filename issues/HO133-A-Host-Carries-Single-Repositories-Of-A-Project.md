# HO133 — A Host Carries Single Repositories Of A Project

**Status:** Implementing.
**Size:** M - the follow's taking narrowed to the repositories the host's card names, one repository taken off the
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

## Open questions for the operator

- **A repository with unpushed work on the host** when taken off the card: is it held until the work reaches the
  central forge, as a project is today (proposed), or taken off at once with the work named as lost?

## To be checked

- The state's form for named repositories, settled with porelo's part before this is built, so both read the same
  field.
- Whether the task gate and a person's push configuration need to know a repository was taken off. A task on a
  repository no longer carried is refused at its start today through the project file.
