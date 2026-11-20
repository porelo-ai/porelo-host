# HO196 — Forge And Matrix Installed And Uninstalled Alone

```json
{
  "$schema": "issue-1.json",
  "id": "HO196",
  "title": "Forge And Matrix Installed And Uninstalled Alone",
  "state": "Estimated",
  "size": "M",
  "priority": "High",
  "rank": 1,
  "blockedBy": ["HO198"],
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
- `uninstall` of the forge: `roles/porelo/tasks/give_back_check.yml` with `porelo_host_give_back_people: false`,
  which asks `porelo-host project give-back-check` and asks again with the follow paused, as `down` does. Then `vm_pool` down, whose runner rents from
  the forge, and `forge` down. Memberships are not checked, since people stay on a host that keeps running.
- `uninstall` of Matrix: `matrix` down alone; no project's work is kept there.
- Neither uninstall takes `base` or `porelo` down; those go only with `down`, which stays as it is.
- On a host, whether the person may uninstall is the window's check before it calls the playbook, since only the
  person's machine knows who the person is: from the organization's signed state, `porelo org --json`, the person
  must be a Machine Admin of that host, and no project the host carries may have project admins that leave the
  person out. The playbook keeps the check of work at central, which only the host can answer.
- A pull request waiting for review does not stop an uninstall: the window warns of it before it calls the playbook,
  and the playbook refuses only while work is not at central.
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

## To be checked

- The field names of a host's admins and carried projects in `porelo org --json`, read from its output before the
  window builds on them.
- Whether `porelo`'s person part assumes a forge or homeserver in what it writes, so that installing one part first
  writes a rule for the other.
