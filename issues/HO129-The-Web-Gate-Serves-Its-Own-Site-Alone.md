# HO129 — The Web Gate Serves Its Own Site Alone

```json
{
  "$schema": "issue-1.json",
  "id": "HO129",
  "title": "The Web Gate Serves Its Own Site Alone",
  "state": "Review",
  "size": "S",
  "priority": "Medium",
  "rank": 23,
  "blockedBy": [],
  "covers": "The web gate refuses a `Host` other than the forge's own site, and on a request that changes something a foreign `Origin` or a cross-site `Sec-Fetch-Site`, so another page in the browser cannot act as the person."
}
```

**Why this size.** one check in `porelo-forge-gate`'s web mode, its unit tests, a Molecule step on the real forge and the
document.

**What must be true.** The web gate signs a request in only when it was made for the forge's own site. Another page open
in the person's browser cannot use the forwarded web port to act as that person, neither by a name that resolves to
loopback (DNS rebinding) nor by a form or script that changes something (cross-site request). The person's own browser
and their tools with a token keep working.

## Plan

- `roles/forge/files/porelo-forge-gate`, web mode, before `Host` is replaced and `X-WEBAUTH-USER` added: read `name` and
  `port` from `/etc/porelo-host/forge.conf`; refuse with `403` a `Host` other than `<name>:<port>` and
  `127.0.0.1:<port>`.
- For a method other than GET and HEAD: refuse with `403` an `Origin` that is present and is not `http://` followed by the
  request's `Host`, and a `Sec-Fetch-Site` that is present and is neither `same-origin` nor `none`. An absent header
  passes: a browser sends both on every cross-site request that changes something, and a laptop client with a token,
  such as Maven or pip through the web port, sends neither.
- A `forge.conf` that cannot be read, that lacks `name` or `port`, or that is not as the role writes it (one
  `key=value` a line, each key once, no whitespace in a value) refuses every web request.
- `git.sock` and `runner.sock` stay as they are: jobs reach the forge through the runner's gate, Git through its own.
- Red first in `tests/unit/roles/test_forge_gate.py`: a foreign `Host`, a foreign `Origin` and a cross-site
  `Sec-Fetch-Site` on a POST are refused before any upstream request; the browser's own headers and a client's without
  either pass.
- Molecule, on the real Forgejo: a person in `porelo-people` fetches `/repo/create` through `web.sock` with a browser's
  headers, posts the form, and the repository exists; the same post with a foreign `Origin` and with
  `Sec-Fetch-Site: cross-site` gets `403` and creates nothing; a page asked for by another name gets `403`, and the
  form opens by `127.0.0.1` without a cookie.

## Acceptance

- The unit tests above, seen failing without the change; Molecule's step green on the VM.

## To be checked

- That the name the person's host card gives the browser is `forge_name` as `forge.conf` holds it: read so far, the
  interface opens `http://<card name>.localhost:<web_port>/` and the role writes `name=<porelo_host_name>.localhost`;
  that the card's name is `porelo_host_name` is not yet read.

## What is built

As the plan says. The laptop's Maven reaches the forge's packages by `http://127.0.0.1:<web_port>/`, which the
document now says, since `localhost` is not the forge's own site and Maven blocks plain HTTP to its name. This Forgejo
renders no `_csrf` field in its forms; it judges a request's origin itself, and the gate's check stands before it.
