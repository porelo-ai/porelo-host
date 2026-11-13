# HO187 — The Host Has A Test Mode Set By Root

```json
{
  "$schema": "issue-1.json",
  "id": "HO187",
  "title": "The Host Has A Test Mode Set By Root",
  "state": "Backlog",
  "size": "M",
  "priority": "High",
  "rank": 9,
  "blockedBy": [],
  "covers": "A host has one place for test switches, `/etc/porelo-host/test-mode.json`, written only by root through the role from `porelo_host_test_switches` and taken away at `down`; its first switch lets Porelo start an uncertified task on a measuring host; the measuring role sets it loudly and only there."
}
```

**Why this size.** One file with a contract that Porelo reads, written and removed by the role, with the switch names
checked at the inventory. A loud line where the host speaks: the check, the up's summary and the card. The measuring
role sets it. Plus the tests and the docs. Porelo's own side is Core's, in an issue of its own.

**What must be true.** [HO186](README.md#ho186)'s `task` and raising steps start stub tasks on a host. A host starts
no task without a certificate signed by a person of its applied organization, and a measuring host has no such
person. The operator decided on 2026-11-13: not a throwaway organization, but a test mode of the host, set by root
only. It is a general place for test switches, since later tests may need to turn other things off. The measure then
writes no person record, so its README's promise stays.

## Found (2026-11-13)

[HO186](README.md#ho186)'s first VM run, at porelo-host 6f28b6d with Porelo `0.5.1~snapshot.508`, made its throwaway
developer, placed the stub, set up the vault and the checkout. Then `porelo task start --agent stub --no-input
--detach` exited nonzero after about ten seconds. The raising step's first developer ended the same way. On a host,
Porelo starts no task without a certificate: "this host starts a task only with a key of its own that you certify".
The host's helper accepts only one signed by the person's current key in the applied organization
([task certificates](../doc/task-certificates.md)). The measuring run's stand-in organization admits nobody.

## Contract (proposed to Core, 2026-11-13)

- **The file.** `/etc/porelo-host/test-mode.json` is a regular file, not a link, owned by root, mode 0644, in a
  root-owned directory that neither group nor others can write. Its content is `{"v": 1, "switches": [...], "why":
  "..."}`. `switches` is an open set: a reader acts only on the names it knows. A file that is missing, of another
  `v`, unreadable, or failing those checks means no test mode.
- **`uncertified-task-start`.** On a host whose file names it, `porelo task start` without a certificate starts
  uncertified instead of refusing. It does not ask the host's helper, since there is nothing to record and no forge
  token. The task carries the `unsigned` mark, and the start says the test mode on stderr each time.

## Plan

- **`porelo_host_test_switches`** (default `[]`, each name from the known ones): `up` writes the file with the names
  and a `why` saying who set it; an empty list removes it. `down` always removes it.
- **Loud:** the host's check and the up's summary name each switch while the file exists.
- **The measuring role** sets `["uncertified-task-start"]` in its own inventory only, and says so in its README; its
  promise about person records stays as it is.
- **Red first:** the role's tests for the file's content, mode and removal, unknown names refused at the inventory,
  and the measure's inventory carrying the switch.

## Acceptance

- A host up with the switch has the file as the contract says, and a host down has none.
- With Porelo's side built, [HO186](README.md#ho186)'s VM run starts its stub tasks and raises its developers.
