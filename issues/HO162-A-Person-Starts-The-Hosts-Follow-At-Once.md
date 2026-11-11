# HO162 — A Person Starts The Host's Follow At Once

```json
{
  "$schema": "issue-1.json",
  "id": "HO162",
  "title": "A Person Starts The Host's Follow At Once",
  "state": "Review",
  "size": "S",
  "priority": "Medium",
  "rank": 3,
  "blockedBy": [],
  "covers": "A person has the host read the organization now, from the window or a command, instead of waiting for the five-minute timer."
}
```

**Why this size.** one sudo rule, the guard that names the rules, one assertion in Molecule's follow act and the
docs; the verb itself is the host program's and is there.

**What must be true.** A person admitted to the host can have it read the organization now, from the window or a
command, instead of waiting up to five minutes for the follow's timer; a change made in the organization reaches the
host within one follow pass of asking. Today only root can start `porelo-host-follow.service`.

## Plan

- **What is there.** porelo 0.5.1~snapshot.462 has `porelo host follow`, which runs `sudo -n porelo-host org
  follow-now` and waits for one pass; porelo-host 462 has `org follow-now`. The collection gives no person the rule.
- **The rule.** `porelo-host-person.sudoers` gets a sixth line, `porelo-host org follow-now`, with no arguments, as the
  forge verbs; its defaults stay. The guard, `tests/unit/roles/test_host_program_boundary.py`'s exactly-the-rules
  test, names six, renamed so, red first.
- **Molecule.** The follow act runs it as the admitted person `fb`, which exits 0 with `org status --json` answering
  after it without a refusal, and as the task account `porelo-fb`, which sudo refuses with nothing started. A second
  request waiting for the first is the host program's, held by its tests in porelo; the act checks it only if it
  can without timing.
- **Docs.** Six rules wherever five are named: `doc/local-forge.md` (its verb list gains `org follow-now`), the
  porelo role's README and `meta/argument_specs.yml`. [HO156](README.md#ho156)'s text stays as the record of what it built.

## Acceptance

- A person's request starts one follow pass and answers when it ended, with its status; a second request while one
  runs waits for it rather than starting another.
- Someone who is not an admitted person, or a task's account, is refused, and nothing is started.

## Measured

On the foo-org host (main at 888d1f0, Ubuntu 26.04), 2026-11-09, as the host's admin, the test identity: `systemctl
start porelo-host-follow.service` answers "Access denied as the requested operation requires interactive
authentication", and the person's sudo rules name no follow; the pass waits for the timer, every five minutes. Once the
collection installs the host's own program, the follow is the host program's `org follow`, so the request belongs to the
host program, and the collection gives a person the one rule to call it.

## Done

- The sixth rule, `porelo-host org follow-now ""`, takes no arguments; the guard names six rules.
- Molecule's default scenario with the forge on, on an earlier package (2026-11-10 16:13Z), went red in the
  follow act: the person's `org follow-now` answered "follow completion unavailable: systemd answered no valid start
  job". On snapshot 474 (main 44068d2 with this change, pool off, 2026-11-10 23:48Z-00:03Z) syntax, converge,
  idempotence, verify and side_effect pass, the follow act's 213 facts among them: `fb`'s request ends a pass with no
  refusal in `org status` and changes nothing on the same state; sudo refuses `nobody` and `fb` with an argument, and
  the refused request fetches nothing. A task's account is the forge's alone and no login on the host, so `nobody`
  stands for the one who is not a person.
- A second request while one runs is the host program's, held by its tests in porelo; the act does not time it.
