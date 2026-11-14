# HO190 — A Released Collection Installs The Host Program Porelo Calls

```json
{
  "$schema": "issue-1.json",
  "id": "HO190",
  "title": "A Released Collection Installs The Host Program Porelo Calls",
  "state": "Backlog",
  "size": "S",
  "priority": "Highest",
  "rank": 1,
  "blockedBy": [],
  "covers": "A collection release from `main` installs the packaged `/usr/sbin/porelo-host`, which `porelo org host refresh` calls, so a machine the window sets up takes the host admin's token; 0.5.12 has only `porelo-host-person`."
}
```

**Why this size.** no code: `main` already installs the packaged host program; a release commit, its hand-over, and a
refresh shown on a fresh Ubuntu 26.04 machine set up from the released collection.

**What must be true.** A machine set up with the released collection answers `porelo org host refresh`: the follow
takes the host admin's token and makes the person's account, so Connect gets past "Waiting for the machine to admit
you".

## Plan

- **What fails today.** The window carries the collection 0.5.12, which installs `/usr/local/sbin/porelo-host-person`
  and no `/usr/sbin/porelo-host`. `porelo org host refresh` runs `env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin ...
  porelo-host org refresh` as root, finds nothing and exits 127; the follow stays `waiting-for-token`. On Ubuntu
  26.04, uutils env 0.10.0 adds "env: use -[v]S to pass options in shebang lines" to every command it cannot find, so
  that line is only a follow-on of the missing program (measured in `ubuntu:26.04`).
- **What `main` has.** The `porelo` role installs the pinned `porelo-host` package, the follow unit runs
  `/usr/sbin/porelo-host org follow`, and `legacy_programs` removes `porelo-host-person` and the other unpackaged
  programs. The name the caller uses is the host's; nothing in the caller changes.
- **The release.** `galaxy.yml` and the changelog to 0.5.13 on `main`'s tested tip, handed over with the next snapshot
  and the signed-tag command for the operator; the window's carried pin moves to it in porelo-frontend.
- **Red first:** a machine set up from 0.5.12 on a local VM: `porelo org host refresh` exits 127 there. Then the same
  from 0.5.13: the refresh hands the token over and the follow answers `following` with the host admin active.

## Acceptance

- On a fresh Ubuntu 26.04 VM set up from the released collection, `porelo org host refresh <host>` exits 0 and
  `porelo-host org status --json` names the organization `following`; nothing in it depends on which env the machine
  has.
- Seen to fail first: the same refresh on a VM set up from 0.5.12.
