# HO17 — The Forge's CA In Porelo's Account

**Status:** Backlog, by the operator's decision of 2026-10-25.
**Size:** XS - one task file in the `porelo` role and its removal at `down`; the two files' paths are agreed with
porelo's [B234](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b234), no contract of its own.

**What must be true.** A task reaches the forge's API through Porelo's broker with a phantom token, and a task
trusts the forge's certificate when it reaches the forge itself.

## Why

Porelo's broker reaches a service of a task only over HTTPS and trusts the CAs Porelo was built with plus every PEM
certificate in the account's `~/.config/porelo/ca-certificates.pem`; an unreadable file is refused. A task trusts a
separate file kept for tasks, `~/.config/porelo/task-ca-certificates.pem`, never the host clients' one, so trusting
the host's forge does not make a task trust an inspecting proxy (porelo's
[B234](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b234), its path and mode agreed in the
channel).

The host's forge serves only HTTPS with a certificate signed by the host's own CA, `/etc/porelo-host/forge/ca.pem`
(`roles/forge/tasks/tls.yml`), so neither the broker nor a task reaches it today.

Accepted by the operator 2026-10-22, from `porelo-project`
[PJ39](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj39)'s planning round. No
per-destination CA for now: the account-wide files are enough until they are seen to fail at something.

## Plan

- **The role `porelo`, a task file `trust.yml`**, included from `tasks.yml` where `porelo_host_forge` is true; it runs
  after the forge in `up`'s second play (`playbooks/up.yml`), so the CA exists:
  - `~/.config/porelo/ca-certificates.pem` of `porelo_account` gets the forge's CA as one block between markers
    (`ansible.builtin.blockinfile`), so the person's own certificates in it stay and a second `up` changes nothing;
  - `~/.config/porelo/task-ca-certificates.pem` holds the forge's CA alone (`ansible.builtin.copy` from the host's
    file);
  - both owned by `porelo_account`, `0600`, the directory `0700`, as Porelo wants them.
- **At `down`** (`roles/porelo/tasks/down.yml`): the marked block taken out of `ca-certificates.pem`, the file removed
  if nothing else is left in it, and `task-ca-certificates.pem` removed.
- **Red first, in Molecule's verify:** both files hold the forge's CA, owner-only, after `up`; the second `up` reports
  no change; after `down` neither holds it. Each assertion seen red without `trust.yml`.
- **`doc/index.md`** names both files.

## Acceptance

- On the test VM `build/molecule.sh` makes: both files of Porelo's account hold the forge's CA, `0600`; a second `up`
  changes nothing; `down` takes the CA out of both. Seen to fail first without the task file.
- With porelo's [B234](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b234) in a published
  snapshot: a task reaches `https://forge.porelo.internal/` and the broker reaches the forge's API with a phantom
  token, measured on the test VM.

## To be checked

- Whether Porelo reads `~/.config/porelo/ca-certificates.pem` at each task start or once per `vault serve` (a running
  vault after `up`).
