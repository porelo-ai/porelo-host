# HO60 — Each Repository's Review Set On The Forge

**Status:** Accepted (operator, 2026-10-30).
**Size:** M - the protection per repository from one value, a dismissed approval, the value read from the project
file in force at bring and at each sync, and Molecule steps for both values and a change between them, with a VM run;
measured M median 63 min.

**What must be true.** The host's local forge protects each repository's `main` according to the value the project
file in force gives that repository under `repositories.<name>.review`:

- **`required`**, also when the key is left out: a pull request is merged only after one approval by a person other
  than its author, and a commit pushed after an approval dismisses it.
- **`optional`**: no approval is needed; the author may merge their own pull request.
- **Either way:** only the forge's teams of owners and developers may merge or approve, never the teams of agents or
  gates; nobody pushes straight to `main`, also not an owner; pull requests are merged by fast-forward only.

## Where the value comes from

Only from the project file the host follows, after Porelo's own follow has verified it against `signers`. Never from
the machine file in the setup directory, which the interface writes and nobody signs, and never from a variable. A
value other than `required` or `optional` refuses, naming the repository; a repository the project file does not
name keeps `required`.

## How a changed value reaches the forge

- The bring sets the protection of each repository as it does today, from the value then in force.
- Root's `sync`, which the project admin's own timer runs after each bundle the interface uploads, compares each
  repository's protection with the value in the project file now in force and sets it back where it differs. Its
  JSON answer names each repository whose protection it changed and to which value; an unchanged sync changes
  nothing.
- A protection that differs and cannot be set refuses the sync loudly, naming the repository; the protection that was
  there stays.
- The forge's readback compares every field the host sets, including the dismissed approval, so a protection changed
  by hand on the forge is set back at the next sync.

## Contract with Porelo (proposed, for Agent Core)

- A Porelo command answers, as JSON, the repositories of the project file in force for a followed project with each
  one's `review`, already checked to be `required` or `optional`. The host reads it there instead of parsing the
  project file itself.

## To be checked

- Which command answers it, and whether root's `sync` reads it as the project admin, as it reads the access file
  today.
- That the forge's `dismiss_stale_approvals` dismisses an approval on a push to the pull request's branch, and that
  `required_approvals: 0` with the merge whitelist still keeps the agents' and gates' teams from merging.
- Whether a pull request open while the value changes from `optional` to `required` keeps its merge button.
