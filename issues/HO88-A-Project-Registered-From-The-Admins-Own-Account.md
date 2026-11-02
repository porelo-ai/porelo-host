# HO88 — A Project Registered From The Admin's Own Account

**Status:** Idea.
**Severity:** high - the interface's Register ends in the host's refusal, so a project is registered only by root on
the host.

**What must be true.** A project admin the applied registry names for a project registers it on the host from their own
account, and the project's forge organization and teams stand before its first `sync`:

- a verb in the person's sudoers rule, checked by the helper to the registry's admin of that project, does what root's
  `porelo-host-project add <project> <admin> --signed-by <key>` does today, and refuses anyone else;
- the registration makes the forge organization with its Owners and developers teams that `porelo.host.bring` makes
  now, so `sync` no longer refuses with "needs Owners and developers teams; run bring first".
