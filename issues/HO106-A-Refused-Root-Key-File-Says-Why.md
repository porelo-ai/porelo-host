# HO106 — A Refused Root Key File Says Why

**Status:** Idea.

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
