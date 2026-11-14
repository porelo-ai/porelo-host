# HO189 — The Move Rehearsal Opens No Room Tunnel

```json
{
  "$schema": "issue-1.json",
  "id": "HO189",
  "title": "The Move Rehearsal Opens No Room Tunnel",
  "state": "Implementing",
  "size": "S",
  "priority": "High",
  "rank": 1,
  "blockedBy": [],
  "covers": "`build/rehearse-move.sh` loses its `tunnel` verb and `build/room-tunnel.sh` goes, with what only they use; the rehearsal otherwise stays as it is."
}
```

**Why this size.** a script, a verb and their unit tests removed, and the documents, the changelog and the issues that
name them corrected; no contract another repository reads.

**What must be true.** Nothing in this repository joins the development machine to a host's tasks: a moved agent talks
only in the host's own room, and the reading before a hand-over is done on the host by a reader started apart from the
task. The move rehearsal does everything else it does today.

## Plan

- **`build/room-tunnel.sh` deleted**, and with it its unit tests in `tests/unit/test_move_tools.py` (the three
  `the_tunnel_…` tests and `run_tunnel`).
- **`build/rehearse-move.sh`'s `tunnel` verb deleted**: its usage lines, its `case` branch with the `tunnel-bin` ssh
  wrapper, and the unit test that calls it (`the_tunnel_takes_only_the_runs_host_key…`). `ssh`, `start`, `down`,
  `rented` and `rented-resume` stay as they are.
- **What only they use** is looked for with `command grep` over the whole tree (`room.sock`, `tunnel-bin`,
  `REHEARSAL_KNOWN_HOSTS`, `ROOM_TUNNEL_ONCE`) and removed; the sshd rule for `porelo-people`'s Unix socket forwarding
  stays, since a person's `return.sock` and `porelod.sock` use it.
- **Documents:** `doc/testing.md`'s `tunnel` line and sentence, `AGENTS.md`'s list of files that cannot be Java, and a
  *Removed* entry in the changelog for `build/room-tunnel.sh`.
- **Issues:** [HO132](README.md#ho132)'s and [HO161](README.md#ho161)'s mentions of the tunnel corrected to what the
  rehearsal does.
- **No test goes red first:** the rehearsal and its tools are test scripts, and a removal guards no harm; the proof is
  the unit suite green without the removed tests, `black --check`, `build/sanity.sh` and the YAML step.

## Acceptance

- `command grep -rn 'room-tunnel\|tunnel-bin\|room\.sock'` over the tracked files finds nothing outside the changelog's
  earlier releases.
- `build/rehearse-move.sh tunnel` ends with the usage line, exit 1.
- The Build's steps green on the commit, run locally each by its own command.
