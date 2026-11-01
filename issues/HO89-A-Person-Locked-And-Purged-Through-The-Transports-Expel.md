# HO89 — A Person Locked And Purged Through The Transport's Expel

**Status:** Idea; blocked by [HO73](README.md#ho73).
**Severity:** high - on a host with the published Matrix transport no person can be locked or purged, so no project
with a person on it is removed and `down` refuses.

**What must be true.** Root's `lock` and `purge`, and every lock that a sync or a project's removal makes, end the
person on the homeserver and on the host:

- the Matrix transport's `expel` gets the homeserver administrator's token on its stdin, in the transport's form of
  secrets, and never on a command line; today it refuses with `78`, and the lock stays pending;
- every command run as the person or a service account starts in `/` with that account's own home, so a lock run by
  root over SSH does not fail where the person cannot enter root's working directory (podman: "cannot chdir");
- Molecule's people tasks lock and purge their persons again and run in the scenario.
