# HO28 — The Forge's Events Routed To Each Account's Porelo

**Status:** Idea. Optional and later: a speed-up only. Each daemon reads what it needs by asking the forge
itself (the operator's decision); a report through this router only makes it arrive sooner.

**What must be true.** The host's forge serves every account on the host, and each account runs its own Porelo daemon
in user mode. An event of the forge about a task's work - a build finished, a pull request merged, reviews and comments
on a task's pull request, the gathered push refused - reaches the daemon of the account whose task it concerns, and no
other: the router verifies each report's signature before anything else, and what reaches the daemon is only a wake-up
hint (repository, pull request number, branch, kind of event) - never content.

- **The forge reports through its own webhooks,** set up by the role as the forge's admin, not by a workflow: a
  webhook lives outside the repositories the agents push, so no task can change what is reported or where.
- **A router on the host** takes the reports at one endpoint, finds the account a task's branch belongs to, and hands
  the report to that account's daemon over its socket. It does nothing else: it starts no task and reads no secret.
- **The router checks `X-Forgejo-Signature`** (HMAC-SHA256 with a secret the role generates on the host and never
  prints) and limits size and rate before it parses JSON; a report that fails is dropped.
- **The account is known from the push:** each daemon pushes with the forge account of its own person
  (the `forge` role makes one per agent today), so the forge names the pusher of every branch, pull request and
  merge, and the role keeps the map from forge account to the host's account.
- **For review and comment events the sender is the reviewer,** so the account is found from the pull request's head
  branch or its author, never from the sender.
- **The daemon decides:** it reads the event's state on
  the forge itself before it acts, so a report too many changes nothing.
- **Nothing from the payload - comment text, identities, a source level, an approval, a deletion - is taken as true:**
  the daemon reads the pull request and its reviews through its forge adapter, and treats comment text as
  untrusted input.
- **A lost report is caught up:** the daemon asks the forge anyway, so a report only makes it quicker.

## Why

A workflow step cannot tell which of the host's daemons a build belongs to, and a job in the runner's container must
not reach any account's socket. One router with one narrow endpoint keeps the accounts apart and the forge's jobs away
from Porelo.
A report carries text anybody with a forge account can write, so it may wake a daemon but never tell it what is true.

## To be checked

- Which Forgejo webhook events the role subscribes - `pull_request`, `pull_request_review_approved`,
  `pull_request_review_rejected`, `pull_request_review_comment`, `pull_request_review_request`, `issue_comment` - and
  their headers `X-Forgejo-Event`, `X-Forgejo-Delivery`, `X-Forgejo-Signature`, to be confirmed against the Forgejo
  version the `forge` role pins in `roles/forge/vars/main.yml`.
- Whether the webhook is a system webhook or one per organization: the role's admin token holds only
  `write:organization` and `write:repository`, so a system webhook needs a wider token or the forge's own command line.
- Whether Forgejo sends a webhook when an Actions run ends; if not, the build's end is reported by a workflow step to
  the same endpoint, and the daemon's own check matters all the more.
- Whether the branch should carry its account as well (`porelo/<account>/<task>`, which Porelo's branch naming allows), so the router needs no map.
