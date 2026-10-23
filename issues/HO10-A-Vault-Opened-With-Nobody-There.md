# HO10 — A Vault Opened With Nobody There

**Status:** Review.
**Size:** XS - the playbook only checks that the vault is open and stops if not; opening it is the caller's, through
Porelo's command.

**What must be true.** `up` runs from start to end without a person opening the vault over `ssh -t`, and the
passphrase still never lies on the host or the person's drive, and never passes through Ansible, its inventory, a
variable or a log.

## Plan

- The stop in `playbooks/up.yml` names `needs: ["vault"]`. The caller, porelo-frontend, answers it by running
  `porelo vault unlock --passphrase-stdin` over ssh with the passphrase on standard input, then runs `up` again.
  The playbook only checks the vault and never reads the passphrase.
- In `extensions/molecule/default/verify.yml`, extend the drive-key search with a passphrase search using a
  protected pattern file, removed in an `always` block. Search the registered `-vvv` output, the whole journal and
  every regular file under `/root`, `/home`, `/srv/porelo-host`, `/etc` and `/var/log`. Exclude and name only
  `/root/.ansible/tmp` and the account's `~/.ansible/tmp`, where the scenario's own commands sit. A search error fails;
  a match reports only its place. The assertion requires every expected place to read clean.
- Red first: the search must name the place of a passphrase written on the host, never the value.

## Acceptance

- The existing shut-vault check observes `needs: ["vault"]`, then the caller unlocks over standard input and `up`
  reaches the end without the playbook reading the passphrase.
- The new passphrase search is [HO10](README.md#ho10)'s acceptance: every listed place is searched and reads clean,
  only the two named Ansible temporary directories are excluded, and any traversal or search error fails closed.
  A leak makes the assertion fail, naming only the affected place.

## Built

- The search in verify, one `grep -lF` per batch of files from `find` with the two exclusions, its error output read
  so that a file or tree it could not read fails the run, never reads clean.
- **Seen red first, by a real leak, 2026-10-23 12:09Z-12:21Z:** the first run found the passphrase in the journal and
  under `/var/log`. The scenario's own `vault init` had it in a shell command without `no_log`, which Ansible logs into
  the journal; on a host the passphrase comes over ssh on standard input past Ansible. Converge now gives it on
  standard input under `no_log`, as verify's unlock does. Green after it, all five stages, 12:22Z-12:36Z, with porelo
  [B258](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b258)'s packages handed over.
