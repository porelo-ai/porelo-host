# HO17 — The Forge's CA In Porelo's Account

**Status:** Accepted.
**Size:** XS - one task in the `porelo` role and its removal at `down`; no contract of its own.

**What must be true.** A task reaches the forge's API through Porelo's broker with a phantom token.

## Why

Porelo's broker reaches a service of a task only over HTTPS and trusts the CAs Porelo was built with plus every PEM
certificate in the account's `$XDG_CONFIG_HOME/porelo/ca-certificates.pem` (`~/.config/porelo/ca-certificates.pem`); an
unreadable file is refused (read in `porelo`'s code by Agent Core, `TrustedCertificates` and `VaultServeCommand`; not
read here).

The host's forge serves only HTTPS with a certificate signed by the host's own CA, `/etc/porelo-host/forge/ca.pem`
(`roles/forge/tasks/tls.yml:14-31,42-63`, `roles/forge/vars/main.yml:7`, `roles/forge/defaults/main.yml:11-12`). So a
task's destination `https://forge.porelo.internal:3000` cannot be reached through the broker today.

Accepted by the operator 2026-10-22, from `porelo-project`
[PJ39](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj39)'s planning round. No
per-destination CA for now: the account-wide file is enough until it is seen to fail at something.

## Plan

- **The role `porelo`** (`roles/porelo`, `porelo_account` in `roles/porelo/defaults/main.yml:3`, run in
  `playbooks/up.yml:57-60` after `porelo.host.forge` at `playbooks/up.yml:51-54`) appends `/etc/porelo-host/forge/ca.pem`
  to `~/.config/porelo/ca-certificates.pem` of `porelo_account` where the forge is set up (`porelo_host_forge`), once
  and idempotently, with the file owner-only (`0600`, owned by `porelo_account`) as Porelo wants it.
- **At `down`** (`roles/porelo/tasks/down.yml`, `playbooks/down.yml:16-20`), the role takes the certificate out again.
- **Red first:** in Molecule, the same request through the broker is refused without the CA in
  `~/.config/porelo/ca-certificates.pem`.

## Acceptance

- On the test VM `build/molecule.sh` makes: a task reaches the forge's API (`https://forge.porelo.internal:3000`)
  through the broker with a phantom token; a second `up` changes nothing (`changed=0`); `down` takes the forge's CA out
  of `~/.config/porelo/ca-certificates.pem`. Seen to fail first without the CA in the file.

## To be checked

- Whether Porelo reads `~/.config/porelo/ca-certificates.pem` at each task start or once per `vault serve` (a running
  vault after `up`).
