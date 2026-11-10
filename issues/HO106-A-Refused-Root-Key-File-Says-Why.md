# HO106 — A Refused Root Key File Says Why

```json
{
  "$schema": "issue-1.json",
  "id": "HO106",
  "title": "A Refused Root Key File Says Why",
  "state": "Review",
  "size": "S",
  "priority": "Medium",
  "rank": 26,
  "blockedBy": [],
  "covers": "`up` refusing root's key file says how many keys it found and what to do, not only `non-zero return code`"
}
```

**Why this size.** two tasks of `base` that count root's keys and say what the file holds, with a unit test on each case.

**What must be true.** When `up` refuses root's key file because it does not hold exactly one ed25519 key, the person is
told that, how many keys it found and what to do, before anything of SSH has changed. Today a server with two root keys,
which a rented one can well be, stops with only `non-zero return code`.

## Why

`roles/base/tasks/ssh.yml` validates the pinned key with a shell command whose failure names nothing, while the metadata
check beside it has a message of its own. Measured on a VM: two ed25519 keys in the file stopped `up` with exit 65 at this
task, and nothing there said why.

## Acceptance

- `up` over a file with two keys, with no key and with a key of another type each stops at this task with words that name
  the file and the fault, without printing a key.
- One ed25519 key still passes.

## Result

Two tasks of their own now count the keys and say what the file holds, in `roles/base/tasks/ssh_key.yml`. A file with two keys says `holds 2 ssh-ed25519 keys and 0 others`,
names the file and says what to do, and prints no key. A key with options before it, or a comment naming `ssh-ed25519` after another key, is refused too: the old check passed them, and the next task would have seeded a broken
line and locked root out. That is the options part of [HO91](README.md#ho91). No SSH state changes before the check, though `base`'s packages come first. The real tasks run in a unit test on each case. A real `up` over such a file was not run after the change; one key passing
is shown by Molecule's `up`.
