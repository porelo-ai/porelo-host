# HO187 — The Measuring Run Stands In An Organization That Admits Its Developers

```json
{
  "$schema": "issue-1.json",
  "id": "HO187",
  "title": "The Measuring Run Stands In An Organization That Admits Its Developers",
  "state": "Backlog",
  "size": "L",
  "priority": "High",
  "rank": 9,
  "blockedBy": [],
  "covers": "The measuring run's throwaway developers start certified tasks on the host, because the run stands in an organization, signed by a key held for the run only, that admits them to `default`; and the measure's promise about person records says what it now writes and takes away."
}
```

**Why this size.** A signed organization tree made for one run, served where the host's follow reads it and applied,
each developer's key admitted and held in an agent at its starts, and all of it taken away again. The measure's
promise that it writes no person record changes, which touches its refusals, its README and its tests.

**What must be true.** [HO186](README.md#ho186)'s `task` and raising steps read numbers on a host. They cannot today.

## Found (2026-11-13)

[HO186](README.md#ho186)'s first VM run, at porelo-host 6f28b6d with Porelo `0.5.1~snapshot.508`, made its throwaway developer, placed
the stub, set up the vault and the checkout. Then `porelo task start --agent stub --no-input --detach` exited
nonzero after about ten seconds. The raising step's first developer ended the same way. The machine is a host, and
on a host Porelo starts no task without a certificate: "this host starts a task only with a key of its own that you
certify". The host's helper accepts only a certificate signed by the person's current key in the applied
organization, for a project the person is a member of ([task certificates](../doc/task-certificates.md)). The
measuring run stands in an organization signed by a key whose private half was thrown away, so the follow never
applies it. There is no applied organization on the machine, and no key a developer could certify with. The task
certificates came after the `task` step was written, and no VM run had read it until this one.

## Plan

- **An organization made for the run:** an admin key made in memory and thrown away when the run ends, a signed
  organization tree naming each throwaway developer with a key of its own and as a member of `default`, served where
  the host's follow reads it, and applied by the follow before the first developer starts.
- **Each developer's key in an agent** for its starts, so Porelo certifies each task as a person's own computer does.
- **Taken away again:** the developers leave the organization and the host, and the run's lock still refuses
  leftovers.
- **The promise reworded:** the README and the refusals say which person records the run writes and removes, and that
  it still refuses any it did not write.
- **Red first** with the `Machine` stand-in; then [HO186](README.md#ho186)'s VM run.

## Acceptance

- On a local VM, the `task` step's samples and the raising step read numbers, or a null with a reason that is not
  the missing certificate.
- Nothing the run made is left after it, the organization included.
