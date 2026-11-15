# HO194 — A Running Up Stops Cleanly Between Its Steps

```json
{
  "$schema": "issue-1.json",
  "id": "HO194",
  "title": "A Running Up Stops Cleanly Between Its Steps",
  "state": "Backlog",
  "size": "M",
  "priority": "Medium",
  "rank": 8,
  "blockedBy": [],
  "covers": "A person who interrupts a running `up` can ask it to stop: it ends the step it is in, starts no further one, says on a line of its own after which step it stopped, and leaves a host that a second `up` resumes and `down` takes back."
}
```

**Why this size.** one strategy plugin, one stop request and one line of the lines callback, a contract with the
host command that reads the lines, `doc/lines.md`, unit tests by the real `ansible-playbook` and one stop on a local
VM.

**What must be true.** A person who interrupts a running `up` can end it so that the host is in a known state: every
described step of `up.yml` is either done or not begun, no package manager, container or unit is left half made, and
the person is told after which step it stopped. A second `up` then runs from the top and finishes; `down` takes the
host back.

## Why

`up` today has no stop. The host command runs `sudo env ... ansible-playbook -c local -i <inventory> porelo.host.up`
in the foreground of one ssh session and reads its lines. An interrupt can only end that session or send the play a
signal. A signal ends the play without waiting for the running task, so an `apt` install, a container start or a
unit's write can be cut in the middle; a closed channel fails the play's next write, and the play may die there or go
on unseen. Neither ends at a known place, and neither says where it ended. Both are expected from reading, not yet
measured (see *To be checked*).

## Plan

- **A stop request**: a root-only file, `/run/porelo-host/up-stop`, which the host command writes over a second ssh
  as the host admin, who already runs `up` with `sudo`. `up`'s first task removes a stale request left by an earlier
  run, so an old stop never ends a new `up`.
- **A strategy plugin `porelo.host.steps`**, the linear strategy with one check: before a task that carries
  `porelo_host_step` (a described step, the only kind `up.yml` runs at its top level), it reads the stop request. With
  one present, it starts no further task, removes the request, sends the callback `v2_porelo_host_on_stopped` with the
  last finished step, and ends the run. A request that comes in the middle of a step waits for the next step's start,
  since a role's inner tasks belong together. `up.yml`'s two plays name `strategy: porelo.host.steps`; `down.yml` does
  not, since its steps must not stop half way.
- **The lines callback** writes `{"v": 1, "state": "stopped", "after": "<task>"}`, `after` naming the last described
  step that ended, or empty before the first; the run ends with exit code 0, and the line, never the code, says it
  stopped, as with the waiting line.
- **Contract with the host command**: the request's path, who writes it, and the `stopped` line; it reads the line and
  tells the person after which step `up` stopped, and that `up` resumes from the top. `doc/lines.md` states both.
- **Red first:** `tests/unit/plugins/strategy/test_steps.py`, by the real `ansible-playbook` on a play of three
  described steps, the first writing the request: the second and third steps leave no trace, one `stopped` line names
  the first, the request is gone and the code is 0. Today the second step runs. Beside it: a request written by a
  step's inner task stops only before the next step; a stale request from before the run stops nothing; a play
  without the request runs to its end exactly as under the linear strategy.

## Acceptance

- The unit tests above, each seen red by taking the check out of the strategy.
- On a local VM: a stop requested while `up` installs the host's packages ends after that step, with `dpkg --audit`
  silent and no half-made unit or container; a second `up` then finishes, and `down` takes the host back.

## To be checked

- What an interrupted `up` does today, measured on a local VM: the ssh channel closed in the middle of a step, and
  `SIGINT` sent through `sudo`: which processes run on, what `dpkg --audit` says, and whether a second `up` and `down`
  go through.
- That the host's `ansible-core` loads a collection's strategy plugin by its full name, and that ending the run from
  the strategy writes Ansible's summary and no failure.
- Whether the host command's interrupt is a closed channel, a signal or both, read in its code before the contract is
  posted.
