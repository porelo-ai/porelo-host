# HO83 — The Person's Token Kept Where Each Tool Reads It

**Status:** Idea; blocked by [HO71](README.md#ho71).

**What must be true.** The person's forge token in their vault is the one in force after every host command that
remakes it, and each check of a task start or a play's token handling fails its test when it is taken away.

## To be checked

- `porelo-host-push` and `--pull` call `forge-token`, which replaces every token of the person, without putting the
  new one into `<forge>.person`: the vault's token no longer works until the next bring or join.
- The host's own principal check counts only `task:` principals: a certificate with a second, other principal passes
  it and reaches Porelo's check; the principal test does not assert that Porelo's check was never run.
- A missing, linked or writable `/etc/ssh/porelo-revoked.krl` at a task start exits 73 and an open failure names
  `/run/porelo-host/sync`; a missing or unsafe host input is 69.
- The test for a host without `porelo` leaves `systemd-run` unchecked.
- The registry revocation test calls the token drop directly instead of `registry`.
- The own-stops test passes with the token file's removal moved out of `always` or with `no_log` dropped.
- `doc/lines.md` names a closing line and the 65 cases of `porelo-host-stop --stdin` that the script does not have.
