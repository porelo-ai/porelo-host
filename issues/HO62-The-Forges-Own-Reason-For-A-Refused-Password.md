# HO62 — The Forge's Own Reason For A Refused Password

**Status:** Idea.
**Replaced:** by the project's one-click joining: the forge has no password any more, so porelo-host-forge-password
goes. Proposed to the operator as Rejected.

**What must be true.** When Forgejo refuses the password `porelo-host-forge-password` sets, the helper's answer gives
Forgejo's own reason with the status, e.g. `the forge refused walkadmin's password (400): <Forgejo's message>`, still
exit 65, and never the password or the token.

## Why

Walk 23: Forgejo refused a 6-character password twice, and the helper said only `the forge
answered 400 setting walkadmin's password`. `set_password` returns the status of an `HTTPError` and drops its body,
where Forgejo names the reason as JSON `{"message": ..., "url": ...}`.

## To be checked

- Only `message` of a 4xx answer, at most 4 KiB read, one line of printable characters, at most 200; dropped when it
  holds the password or any part of it of 4 characters or more. A 5xx answer, or no usable message, keeps today's words.
- Forgejo's real text for a too short password, read once on the VM.
