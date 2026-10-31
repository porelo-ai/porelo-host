# HO83 — The Person's Token Kept Where Each Tool Reads It

**Status:** Review; blocked by [HO71](README.md#ho71).
**Size:** S - one line of the push, one helper check and the tests that pin six existing checks.

**What must be true.** The person's forge token in their vault is the one in force after every host command that
remakes it, and each check of a task start or a play's token handling fails its test when it is taken away.

## Plan

- `roles/forge/files/porelo-host-push`: after `forge-token`, the token goes on a pipe into
  `porelo vault put <forge>.person` with the caller's home and runtime directory; a refusal is said and the push goes
  on.
- `roles/forge/files/porelo-host-push` reads the forge's name before the token is made anew and puts only a token of
  40 hex digits into the vault.
- `roles/porelo/files/porelo-host-person`: a task certificate must name exactly one principal, `task:<project>:<task>`;
  a missing, linked, writable or unreadable KRL is 69 naming it, read by one descriptor closed on every path; the uncalled token drop of the
  registry goes, since registry revocation locks the person.
- Tests: the push's vault stand-in sees the token on stdin and the caller's environment; the principal cases assert
  that Porelo's check never ran; the KRL cases expect 69; both `porelo` and `systemd-run` are required; own.yml's
  token task is `no_log` and its file is removed in `always`. `doc/lines.md` names the stop's real closing line and its
  65 cases.

## Acceptance

- [ ] after a push, `<forge>.person` in the vault is the token in force; a closed vault is named and the push is done;
- [ ] each check above, taken away, turns its test red.
