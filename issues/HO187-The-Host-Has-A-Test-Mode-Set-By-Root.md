# HO187 — The Host Has A Test Mode Set By Root

```json
{
  "$schema": "issue-1.json",
  "id": "HO187",
  "title": "The Host Has A Test Mode Set By Root",
  "state": "Backlog",
  "size": "M",
  "priority": "Medium",
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

## Contract (agreed with Core, 2026-11-13; Porelo's side is B717)

- **The file.** `/etc/porelo-host/test-mode.json` is a regular file, not a link, owned by root, mode 0600, in
  root-owned directories that neither group nor others can write. Its content is `{"v": 1, "switches": [...], "why":
  "..."}`. `switches` is an open set: the host program acts only on the names it knows. A file that is missing, of
  another `v`, unreadable, or failing those checks means no switch at all. Porelo never reads it.
- **Asking.** `sudo porelo-host test-switches --json` answers `{"switches": [...]}`, exit 0, or 64 on wrong use. An
  older host program without the verb counts as no switches.
- **`start-uncertified`.** While it is on, `porelo-host task start <task>` with an empty standard input starts the
  task without a certificate, for a `porelo-people` caller whatever the organization says, in the project `default`,
  and records it as uncertified; without the switch it is refused with 65. `porelo task start` warns, asks unless
  `--yes`, and refuses without a terminal and without `--yes`. `task end` keeps the record; the measure removes
  `/var/lib/porelo-host/tasks/<login>/` itself with the account.

## Plan

- **`porelo_host_test_switches`** (default `[]`, each name from the known ones, today `start-uncertified`): `up` writes the file with the names
  and a `why` saying who set it; an empty list removes it. `down` always removes it.
- **Loud:** `up` says `TEST MODE` and each switch on a note line of its own while the file exists.
- **The seventh sudo rule:** `%porelo-people ALL=(root) NOPASSWD: /usr/sbin/porelo-host test-switches --json`.
- **The measuring role** sets `["start-uncertified"]` in its own inventory only, and says so in its README; its
  promise about person records stays as it is.
- **Red first:** the role's tests for the file's content, mode and removal, unknown names refused at the inventory,
  and the measure's inventory carrying the switch.

## Built so far (2026-11-13)

- **The role's side.** The `porelo` role's person entry writes the file from `porelo_host_test_switches` (refusing
  any other name than `start-uncertified`, and non-lists) with `porelo_host_test_why`, mode 0600, and says `TEST
  MODE` on a note line; an empty list takes it away. `down` removes it first of all, plainly and before any check
  may refuse, in the playbook and in the role. A link where the file goes is replaced, never written through. The seventh sudo rule is in, and the docs name
  it ([task certificates](../doc/task-certificates.md#test-mode), the role's README, the local forge page).
- **The measure.** Its inventories set `start-uncertified` with a `why` naming the measure, its starts pass
  `--no-input --yes`, and the teardown removes the host's records of the developer's starts, refusing to go on if
  they stay.
- **Tests.** Six role tests over the real tasks and the specs (the file, its removal, names and shapes refused, a
  link replaced, down's first plain removal and the sudo rule, the known switch), the sudo-rule test at seven, and a
  measure test for the switch, `--yes` and the records. A Sonnet reading found no Red; its Yellows are in.
- **Not yet:** a VM run, once Core's B717 is in a snapshot.

## Acceptance

- A host up with the switch has the file as the contract says, and a host down has none.
- With Porelo's side built, [HO186](README.md#ho186)'s VM run starts its stub tasks and raises its developers.
