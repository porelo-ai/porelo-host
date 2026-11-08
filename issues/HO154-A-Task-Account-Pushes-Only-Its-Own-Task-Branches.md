# HO154 — A Task Account Pushes Only Its Own Task Branches

**Status:** Review.
**Size:** S - one rule in the push judge, one field in the forge's hook, their tests and a paragraph of the doc.

**What must be true.** A task's token may push and force-push `porelo/<task>` of its own person's tasks on the host's
forge, as an amend pushed with a lease does, and no other ref: not another person's task branch, not `main`, not a tag
and not a new branch.

## Why

The task token belongs to `porelo-<login>`, a member of the project's `developers` team with `write` on its
repositories. Branch protection covers `main` alone. So the token could push or force-push any other branch of every
repository of the organizations that account is in, another person's `porelo/<task>` among them. Only Porelo's task
gate, which names the ref, held a task to its own.

Forgejo tells a hook which account pushed, not which token. So the host can hold an account to its person's tasks,
but not one task of a person apart from another.

## Plan

- The forge's pre-receive hook sends `pusher <GITEA_PUSHER_NAME>` with its other fields. The judge requires the field.
- `verify-push` refuses with 403, before any commit is judged and for a deletion too, an update from `porelo-<login>`
  (a person of the host) to a ref other than `refs/heads/porelo/<task>` of a task recorded for `<login>`.
- A person's own account, an account of no person (`porelo-publisher-<project>`) and an empty pusher are judged as
  before.
- Force stays allowed: the judge asks for no fast-forward and judges the new commits' signatures.

## Acceptance

- Tests, seen red first:
  - the hook sends the pusher;
  - a task account force-pushes its own task branch and is judged;
  - it is refused, without a judgement, for another of its person's names, another person's task, `main`, a new
    branch, a deeper ref and a tag;
  - it is refused when deleting another's task branch;
  - a person, a publisher and an empty pusher push as before.
- On a host, in Molecule: a task's amend pushed with a lease reaches its branch, and its token is refused a branch of no
  task of its person, which proves Forgejo names the pusher to the judge.
