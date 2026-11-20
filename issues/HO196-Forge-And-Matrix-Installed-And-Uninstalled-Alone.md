# HO196 — Forge And Matrix Installed And Uninstalled Alone

```json
{
  "$schema": "issue-1.json",
  "id": "HO196",
  "title": "Forge And Matrix Installed And Uninstalled Alone",
  "state": "Analyzed",
  "size": "M",
  "priority": "High",
  "rank": 1,
  "blockedBy": [],
  "covers": "The forge and the Matrix homeserver are each installed and uninstalled alone, by one playbook taking the part and the action, the same on a host and on a person's own computer; uninstalling one leaves the other and everything both share, and uninstalling the forge refuses while a project's work is not at its central forge."
}
```

**Why this size.** One new playbook beside `up` and `down`, the refusal checks per part, the documents and a Molecule
scenario that installs and uninstalls each part alone: M.

**What must be true.** A person installs the forge or Matrix from that part's own page in the window, and uninstalls it
there, each without touching the other. The window calls one command with the part and the action, and reads the same
JSON lines `up` and `down` print (`porelo.host.lines`): what runs, a waiting stop for what only the person can give, a
refusal, done. Uninstalling the forge is refused while any project's work on it is not at its central forge.
Uninstalling either part leaves what the other part and the host's own setup need. Today `down` takes the whole host
at once; the roles' down steps already take down only what is there, so they serve a single part as they are.

## Plan

- `playbooks/part.yml`: one playbook taking `porelo_host_part` (`forge` or `matrix`) and `porelo_host_action`
  (`install` or `uninstall`), each refused unless it is one of these. The inventory's version, name and network are
  checked as in `up`.
- `install`: the check role asks only for that part. `base` and `porelo`'s install run as in `up`'s first play, since
  both parts need podman, subordinate ids and the `porelo-people` group. Then the part's role runs, then `porelo`'s
  person part and `base`'s host summary, so the people's sudo rules and the summary name what now runs. The forge
  part sets `porelo_host_forge` for the run; the inventory value stays what `host up` wrote.
- `uninstall` of the forge: the checks of `down`'s first block, reduced to the forge: `porelo-host project
  give-back-check`, asked again with the follow paused, as `down` does. Then `vm_pool` down, whose runner rents from
  the forge, and `forge` down. Memberships are not checked, since people stay on a host that keeps running.
- `uninstall` of Matrix: `matrix` down alone; no project's work is kept there.
- Neither uninstall takes `base` or `porelo` down; those go only with `down`, which stays as it is.
- Red first, a unit test in `tests/unit` that reads the playbook as YAML:
  - an unknown part or action stops before any role;
  - the forge's uninstall runs `give-back-check` before any down task;
  - Matrix's uninstall includes no forge or pool task.
- Molecule: one scenario.
  - It installs Matrix, then the forge.
  - It uninstalls the forge and finds Matrix still answering.
  - It uninstalls Matrix and finds no account, unit or volume of either left.
  - A second converge of each install changes nothing.
- `doc/index.md` and `doc/lines.md`: the part playbook, its variables and its lines.

## Acceptance

- The unit test above, seen red first, and the Molecule scenario pass on the local VM.
- On a rented host with both parts, the forge is uninstalled while a project's branch is ahead of central: refused,
  naming the project. Once the work is at central, it is uninstalled, and Matrix still answers.

## Open questions

- Whether uninstalling the forge warns, rather than refuses, while a pull request waits for review, as the design
  asks. The playbook can only refuse or go on; a warning belongs to the window, which would read the open reviews
  before it calls the playbook. Proposed: the window warns, and the playbook refuses only for work not at central.

## To be checked

- Where a host's Machine Admin check runs, and how the window learns that another person's project uses the forge:
  `give-back-check` names projects, not their owners. To be asked of Agent Core and Agent Frontend.
- Whether `porelo`'s person part assumes a forge or homeserver in what it writes, so that installing one part first
  writes a rule for the other.
