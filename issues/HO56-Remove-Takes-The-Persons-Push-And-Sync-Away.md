# HO56 — Remove Takes The Person's Push And Sync Away

**Status:** Accepted.
**Size:** M - remove reaching into each person's account, with a VM run; measured M median 63 min.

**What must be true.** Removing a project from the host takes away, in each person's own account, what the bring and
join left for it: the push config of [HO47](README.md#ho47) and the sync timer of [HO46](README.md#ho46). Today both
stay, and the timer's `sync` refuses the unregistered project at each run until purge deletes the account.

## What is seen

The pass over 6j–6l names it in `doc/guides/6-host.md` under "What the host does not do yet".

## What stays open

Whether remove reaches into each account itself, or each person's next bring or sync takes away what no registered
project names.
