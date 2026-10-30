# HO60 — Each Repository's Review Set On The Forge

**Status:** Backlog (operator, 2026-10-30).
**Size:** M - the protection per repository from one value, a dismissed approval, the value read from the project
file in force at bring and at each sync, and Molecule steps for both values and a change between them, with a VM run;
measured M median 63 min, from three M builds (47, 63, 75).

**What must be true.** The host's local forge protects each repository's `main` according to the value the project
file in force gives that repository under `repositories.<name>.review`, and the project's own repository's `main`
according to `project.review`, with the same meaning:

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

## Contract with Porelo (agreed with Agent Core)

- `porelo project verify --json`, which root's `sync` already runs on the admin's bundles in its isolated unit,
  answers beside its fields of today:
  - `"repositories": {"<name>": {"review": "required" | "optional"}, ...}`: every repository the project file names,
    in the order written, a missing key answered as `"required"`; `{}` for a project without repositories;
  - `"project_review": "required" | "optional"` for the project's own repository, a missing key answered as
    `"required"`. The string field `"project"` stays as it is.
- A value other than the two is refused by verify with exit 65 before anything is answered, naming the key.
- `porelo project following --json` stays as it is; the host never parses the project file itself.

## To be checked

- Whether the bring takes the value from the same verify answer, or from the follow it has just made.
- That the forge's `dismiss_stale_approvals` dismisses an approval on a push to the pull request's branch, and that
  `required_approvals: 0` with the merge whitelist still keeps the agents' and gates' teams from merging.
- Whether a pull request open while the value changes from `optional` to `required` keeps its merge button.
