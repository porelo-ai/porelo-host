# HO85 — The Push Judge Armed Only Where It Holds

**Status:** Review; blocked by [HO76](README.md#ho76).
**Size:** S - checks in the arming script, the removal's arrivals, one lock, the verdict's fields, handler order and
tests.

**What must be true.** A repository is recorded as armed only when its hook link names the mounted hook, which is
there and executable, and no link stands on its way; a forge without the repositories' directory stops the arming. A
project's removal takes its arrivals along. Reading arrivals holds the lock the writers hold, and every record and its
directory are checked root's and private before a read. A verdict is recorded only with a valid arrival time, commit
and signer fingerprint, and the KRL is read only when it is root's regular file. The push judge's socket restarts
before Forgejo, and a push mixing a deletion with an update is judged. The texts name the socket as the forge
account's and the mount as the directory's.

## Acceptance

- [ ] a repository whose hook link names anything but the mounted hook stops the sync's arming, recording nothing;
- [ ] removing a project leaves no `arrivals/<project>` behind;
- [ ] a push of a deletion and an unsigned update is refused.

## Plan

- The arming script requires the repositories' directory, refuses a linked organization, hooks directory or
  `pre-receive.d`, links only where nothing stands, and requires the link to name the mounted hook and to be
  executable; an organization with no directory arms nothing.
- `porelo-host-project remove` checks `/var/lib/porelo-host/arrivals/<project>` root's and private before the forge
  is touched, and removes it with the project's records.
- `arrivals` reads under `forge.conf`'s shared lock; the record's directories and files are checked `0700`/`0600`
  root's before a read, and only `<repository>.jsonl` entries are taken.
- A verdict needs a `checked_at` time, a string commit and a signer fingerprint; the KRL's descriptor is checked
  root's plain file.
- The push judge's socket handler runs before Forgejo's; `/usr/local/libexec` is made by one task.
- Tests: each arming refusal by a real `sh` run, a mixed push, sync calling the arming, the removal, the lock, the
  verdict fields; each check's removal is noticed, except the KRL's and the record's `fstat`, which the path checks
  before them already refuse.
