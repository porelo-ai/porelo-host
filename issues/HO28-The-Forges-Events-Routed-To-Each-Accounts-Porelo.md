# HO28 — The Forge's Events Routed To Each Account's Porelo

**Status:** Idea. Optional and later: a speed-up only. Each daemon reads what it needs by asking the forge
itself (the operator's decision); a report through this router only makes it arrive sooner.

**What must be true.** The host's forge serves every account on the host, and each account runs its own Porelo daemon
in user mode. An event of the forge about a task's work - a build finished, a pull request merged, a comment written,
the gathered push refused - reaches the daemon of the account whose task it concerns, and no other.

- **The forge reports through its own webhooks,** set up by the role as the forge's admin, not by a workflow: a
  webhook lives outside the repositories the agents push, so no task can change what is reported or where.
- **A router on the host** takes the reports at one endpoint, finds the account a task's branch belongs to, and hands
  the report to that account's daemon over its socket. It does nothing else: it starts no task and reads no secret.
- **The account is known from the push:** each daemon pushes with the forge account of its own person
  ([HO26](README.md#ho26) makes one per agent today), so the forge names the pusher of every branch, pull request and
  merge, and the role keeps the map from forge account to the host's account.
- **The daemon decides,** as `porelo` [B288](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b288),
  [B289](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b289) and
  [B290](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b290) say: it reads the event's state on
  the forge itself before it acts, so a report too many changes nothing.
- **A lost report is caught up:** the daemon asks the forge anyway, so a report only makes it quicker.

## Why

A workflow step cannot tell which of the host's daemons a build belongs to, and a job in the runner's container must
not reach any account's socket. One router with one narrow endpoint keeps the accounts apart and the forge's jobs away
from Porelo.

## To be checked

- Whether Forgejo sends a webhook when an Actions run ends; if not, the build's end is reported by a workflow step to
  the same endpoint, and the daemon's own check matters all the more.
- Whether the branch should carry its account as well (`porelo/<account>/<task>`, as `porelo`
  [B190](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b190) allows), so the router needs no map.
