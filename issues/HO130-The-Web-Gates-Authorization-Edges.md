# HO130 — The Web Gate's Authorization Edges

**Status:** Idea.

**What must be true.** On `web.sock`, a request with an `Authorization` header is a token client's: an empty or malformed
header is refused as on `git.sock`, only the `Basic` and `token` schemes pass, and no cookie goes beside a token. Today
an empty `Authorization:` lets a request to a route signed in only by a token skip the gate's `401`/`403` while the
browser's cookie still reaches Forgejo, and `Bearer` passes although only the runner's socket takes it. The gate's
refusals of a second `Authorization` header and of a request target that is not a path (`http://…`, `//…`, one with
`#`) hold, but no test fails without them.
