# HO81 — The Gate's Route Match Holds For Every Decoded Byte

```json
{
  "$schema": "issue-1.json",
  "id": "HO81",
  "title": "The Gate's Route Match Holds For Every Decoded Byte",
  "state": "Review",
  "size": "XS",
  "priority": "Medium",
  "rank": 36,
  "blockedBy": [],
  "covers": "No decoded byte takes a refused route past the forge gate's match, and `web.sock` challenges a client that waits for one."
}
```

**Why this size.** one module (the forge gate): a stricter path check, two patterns and one answer, with unit tests.

**What must be true.** No byte a request's path decodes to takes a refused route of the forge gate past its match.
A package or Git client on `web.sock` that waits for a challenge before it sends its token gets one.

## Analysis

The fourth reading of the forge's gate found two things.

- **A decoded control character escapes the match.** `%0a` is a valid escape, so `unsafe_path` passes it. The gate's
  patterns end in `(/.*)?`, compiled without `re.DOTALL`, and `.` does not match the decoded newline. Forgejo's
  router keeps `%0a` inside its segment and routes the request. Examples:
  - `DELETE /api/v1/users/alice/tokens/tok%0a` reaches the token route on any socket;
  - `GET /<owner>/<repo>/info/lfs/objects/<oid>/file%0a` on `web.sock` without a token is signed in by the gate's
    `X-WEBAUTH-USER`.
- **No challenge on `web.sock`.** It answers `403` to Git, LFS and package routes without an Authorization header.
  Package links point at `ROOT_URL`, the web port. Maven, which sends no credential before it is challenged, and pip
  then stop at the `403` and never send their configured token.

## Plan

- `unsafe_path` refuses with `400` a path whose decoded segments hold a control character (`\x00`-`\x1f`, `\x7f`).
- The route patterns are compiled with `re.DOTALL`, so a decoded byte never ends a match early.
- `web.sock` answers a Git, LFS or package route without an Authorization header with `401` and
  `WWW-Authenticate: Basic`, as `git.sock` does, and still never signs it in. A browser, known by its `Sec-Fetch-*`
  headers, gets `403`, so a page's embedded LFS file or a "View Raw" link never prompts for a password.
- `user/` is no owner in the Git pattern, so an avatar of a person named `head` or `objects` stays a page.
- Red first in `tests/unit/roles/test_forge_gate.py`: `%0a` behind a token route and an LFS route, and the challenge
  for an unauthenticated Maven metadata request on `web.sock`.

## Acceptance

- A refused route with `%0a`, `%0d` or `%09` in a later segment is refused on every socket. Seen to fail: the tests
  against the forge's gate.
- `GET /api/packages/<owner>/maven/.../maven-metadata.xml` without a token on `web.sock` answers `401` with a Basic
  challenge and reaches no upstream.
