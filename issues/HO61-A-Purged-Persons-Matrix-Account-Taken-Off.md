# HO61 — A Purged Person's Matrix Account Taken Off

**Status:** Backlog.
**Size:** S - finding and deactivating, or naming, the person's account on the host's homeserver at purge, with a
unit test and a VM run; measured S 54 min, from one S build only, so nearly a guess. The homeserver's admin
interface is the open part and could make it M.

**What must be true.** When `porelo-host-person purge` removes a person, their account on the host's own Matrix
homeserver goes too, or the purge names it as left. Today it may stay without a word.

## Why

This was filed when purge only cleared the person's vault and accepted an account the transport kept, so a removed person
kept an account on the homeserver that nobody was told about. Purge has since come to run the transport's `expel` before
anything else is removed, and a refusal stops the purge. Only unit tests and a run without such an account said so.

## What is shown

The purge needed no change. On the test VM a person made their own account and a task's through the gate, as a client
does; both tokens acted (`200`, which shows the question can tell), and after `porelo-host-person purge` the homeserver
refused both (`401`), with the login kept taken. Both accounts belong to one purged person of the follow's act.

## Answered

- **Root may deactivate them,** through the transport's `expel` run as the homeserver's account with the gate's
  administrator token, finding them by login: the person's own and every `*.<login>`.
- **Purge deactivates them,** and names nothing left.
