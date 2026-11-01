# HO89 — A Person Locked And Purged Through The Transport's Expel

**Status:** Implementing.
**Size:** M - one helper and its tests, the transport's secrets form, and the Molecule scenario's people again.
**Severity:** high - on a host with the published Matrix transport no person can be locked or purged, so no project
with a person on it is removed and `down` refuses.

**What must be true.** Root's `lock` and `purge`, and every lock that a sync or a project's removal makes, end the
person on the homeserver and on the host:

- the Matrix transport's `expel` gets the homeserver administrator's token on its stdin, in the transport's form of
  secrets, and never on a command line; today it refuses with `78`, and the lock stays pending;
- every command run as the person or a service account starts in `/` with that account's own home, so a lock run by
  root over SSH does not fail where the person cannot enter root's working directory (podman: "cannot chdir");
- Molecule's people tasks lock and purge their persons again and run in the scenario.

## Plan

- `roles/porelo/files/porelo-host-person`: `as_account` and `porelo` run `runuser -u <account> -- env -C / HOME=<home>
  …`, so no call as another account keeps root's working directory or HOME.
- `matrix_expel_revoke` reads the homeserver administrator's token as `porelo-matrix` and passes
  `{"secrets":{"PORELO_MATRIX_ADMIN_TOKEN":"<token>"}}` on expel's stdin; a missing or empty token refuses by name
  before any change, and the token is in no argv, environment, file or output.
- Red first in `tests/unit/roles/test_porelo_host_person*.py`: a call as another account without `-C /` or the
  account's HOME, and expel called without the secrets on stdin.
- `extensions/molecule/default/verify.yml`: people.yml runs again, no longer `notest`.

## Acceptance

- The unit tests above, seen red then green, and the full helper suite.
- Molecule on `ubuntu26.04`: people.yml locks and purges its persons, and `down` passes.

## To be checked

- Which file holds the token expel needs, asked of the Matrix transport's agent.
