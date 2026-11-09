# HO162 — A Person Starts The Host's Follow At Once

**Status:** Backlog.

**What must be true.** A person admitted to the host can have it read the organization now, from the window or a
command, instead of waiting up to five minutes for the follow's timer; a change made in the organization reaches the
host within one follow pass of asking. Today only root can start `porelo-host-follow.service`.

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
