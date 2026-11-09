# HO161 — A Local Rehearsal Pins The Host Admin's Key For Root

**Status:** Idea.

**What must be true.** A local rehearsal with a real organization's machine file leaves root's login to the host
admin's key, as a person's window does on a rented server, so `org host refresh` reaches the host with the admin's
own agent. Today root holds only the run's key, `refresh` is refused with "Permission denied (publickey)", and up
refuses a second ed25519 key beside it, so the run's key has to be replaced by hand.

## Acceptance

- After a start with a machine file, `org host refresh` from the admin's agent hands its token over without a step by
  hand, and `ssh`, `tunnel` and `down` still reach the VM through the run's own login.
