# HO17 — The Forge's CA In Porelo's Account

**Status:** Review.
**Size:** XS - one task file in the `porelo` role and its removal at `down`; the two files' paths are agreed with
porelo's [B234](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b234), no contract of its own.

**What must be true.** Porelo's forge reader on the host, outside every task, trusts the local forge when reading
builds; reading comments and merges through that host path is pending in
[B171](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b171) and
[B289](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b289).
Separately, a task trusts declared host services such as the registry, and its declared access to the forge's API
uses the broker with a phantom token.

## Why

The forge reader runs on the host and receives its credential from Porelo's vault for each call; it does not run
inside a task or use a task's phantom token. Its host-side trust applies to build reads and is separate from the
pending comment and merge readers. See the
[build-reader contract](https://github.com/porelo-ai/porelo/blob/main/doc/build-readers.md).

For a task's declared service access, Porelo's broker reaches the destination over HTTPS and substitutes the real
credential for the task's phantom token. The broker trusts the built-in CAs plus the account's
`~/.config/porelo/ca-certificates.pem`; an unreadable file is refused. A task reaching a declared host service such
as the registry trusts a separate file, `~/.config/porelo/task-ca-certificates.pem`, never the host clients' one,
so trusting the host's forge does not make a task trust an inspecting proxy. Porelo validates and copies the task
file into private task state and installs the authority in the task's trust store
([credentials](https://github.com/porelo-ai/porelo/blob/main/doc/credentials.md),
[B234](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b234)).

The host's forge serves HTTPS with a certificate signed by `/etc/porelo-host/forge/ca.pem`
(`roles/forge/tasks/tls.yml`). The role's `trust.yml` supplies that CA to both account files, so the host clients
and tasks can validate the certificate through their separate trust paths. Trust alone grants neither network
access nor a credential. The account-wide files suffice without per-destination CA configuration.

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
