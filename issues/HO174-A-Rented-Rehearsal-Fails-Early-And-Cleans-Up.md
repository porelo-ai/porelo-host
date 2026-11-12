# HO174 — A Rented Rehearsal Fails Early And Cleans Up

```json
{
  "$schema": "issue-1.json",
  "id": "HO174",
  "title": "A Rented Rehearsal Fails Early And Cleans Up",
  "state": "Backlog",
  "size": "S",
  "priority": "High",
  "rank": 1,
  "blockedBy": [],
  "covers": "build/rehearse-move.sh's rented mode probes its organization and token programs before it claims a server, lets a second run onto a server a clean down left, and takes its read keys off central for the organization the machine file names."
}
```

**Size S.** One test script, `build/rehearse-move.sh`, and the agents' start scripts; no production code.

**What must be true.** A rented rehearsal that cannot reach the organization stops before it touches the server, a
second run on the same rented server is possible after a clean `down`, and nothing of a run stays at central.

- **The programs are probed first.** Today the organization program's `--version` is asked only in the `org` step,
  after the server was claimed and `up` ran; a start that did not pass the client's version failed there. The rented
  mode asks the organization program's `--version` and runs the central token program before `refuse-existing`, and
  stops naming the one that did not answer. A start script fails at once on a missing `PORELO_CLIENT_SNAPSHOT`.
- **A clean down lets a rerun in.** `down` leaves `/etc/porelo-host`, since the software stays until the server is
  deleted, and the guard refuses any server holding it, so a rerun needed it moved by hand. Once the rented `down` ran
  clean, it renames `/etc/porelo-host` to `/root/porelo-host-down-<stamp>` with the run's owner token beside it. The
  guard takes a server whose only trace is such a rename, and still refuses one with a live `/etc/porelo-host`.
- **The read keys leave central.** The run skips the read (deploy) keys for the operator's own script, which reaches
  only the operator's organization, so a run against a test organization left its keys there. The rented `down` takes
  off the keys titled for its host and made within its run, with the test identity's token, for the organization the
  machine file names, and lists them again to show none is left. The operator's own script, kept outside this
  repository, takes the owner as an argument; that change is the Coordinator's.

## Plan

- `build/rehearse-move.sh`, rented mode: the two probes before `refuse-existing`; the rename at the end of a clean
  `down`; the guard's exception for the rename; a `read-keys` step after `down` in place of today's SKIP line.
- The agents' start scripts: `${PORELO_CLIENT_SNAPSHOT:?}` in the start script itself.
- A test script: no red-first and no unit suite of its own. Its proof is the next rehearsal run on a VM.

## Acceptance

- On a local VM in rented mode: a start without the client's version stops before `refuse-existing`; a second run on
  the same VM after a clean `down` passes the guard; the run's read keys at the test organization are gone after
  `down`, shown by the list after.
