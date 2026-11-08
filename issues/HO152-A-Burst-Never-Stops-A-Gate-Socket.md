# HO152 — A Burst Never Stops A Gate Socket

**Status:** Review.
**Size:** XS - five socket templates, two checks in up, one test file.

**What must be true.** A burst of connections never stops one of the host's gate sockets for good: the forge's web,
git and runner gates, the push judge and the Matrix client gate. Each says how many connections it takes at once, and
*up* fails when a gate socket is not listening, rather than the person's browser or Element finding out.

## Why

During a rental the forge's page went empty (ERR_EMPTY_RESPONSE through the window's forward) while three Builds ran.
It did not come back until the host was given back. The ssh connection and its git forward kept working, and Forgejo
answered through the git gate, so only `porelo-forge-web.socket` was gone.

Each gate socket is `Accept=yes`: one process for every connection, each answering one request. None set
`TriggerLimit…`, so systemd's default held: 200 starts in 2 s. When that limit is hit, systemd fails the socket unit,
`RemoveOnStop` deletes its path, and every later channel the forward opens ends with no byte.

The poll limit (by default 150 wakeups in 2 s on each listening socket) pauses accepting for the rest of its window
and then goes on. It slows a burst, but a burst spanning two of its windows still reaches 200 starts within one
2-second trigger window.

The journal went with the server, so this is read from the code, not seen. The page staying empty fits the trigger
limit and not the 64 connections at once, which clear by themselves.

## Plan

- Each `Accept=yes` socket template sets `TriggerLimitIntervalSec=0`, which systemd reads as no trigger limit, so no
  rate of connections fails it.
- The people's and the runner's gates set `MaxConnections=256`; the push judge keeps its 16. A connection over the
  bound is closed and the socket goes on listening.
- The poll limit stays at systemd's default: it pauses and recovers by itself.
- After the forge gate sockets and the push judge start, and their handlers have run, *up* checks that each unit is
  active and its path is a socket. The Matrix role does the same for its gate.
- Not here: keeping a browser connection open for several requests, so a page starts fewer processes.

## Acceptance

- `tests/unit/roles/test_gate_socket_limits.py`, seen red first, checks that:
  - every `Accept=yes` template under `roles/` is found, sets `TriggerLimitIntervalSec=0` and sets its
    `MaxConnections` (256, the judge 16);
  - both listening checks name every unit and path, run `systemctl is-active` and `test -S`, are never skipped, and
    run after the units start and a handler flush.
- `systemd-analyze verify` takes the rendered socket units without a word.
