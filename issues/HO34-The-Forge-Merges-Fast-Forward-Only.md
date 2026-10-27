# HO34 — The Forge Merges Fast-Forward Only

**Status:** Implementing.
**Size:** S - one task in the role `forge`'s `protection.yml` that sets and reads back each repository's merge
styles, Molecule's check of them, and the role's README.

**What must be true.** A pull request merged on the host's forge puts its own commits on `main` unchanged, with their
author, signature and message, and no commit of the forge's own. What `porelo-host-push` later carries to the public
`main` then names the person as its author, never the forge's `operator` account. Each commit also meets the shared
rule on commit messages that the Build checks on the push.

## What was measured

Sprint 5's rented host, 2026-10-27:

- The operator merged porelo-buildtools pull request 1 with Forgejo's default style. The forge made a merge commit,
  `46df8fc`, whose author is `operator <operator@forge.porelo.internal>`. Its subject is "Merge pull request
  'Publish this copy's snapshot into the host forge's registry' (#1) from sprint5/publish into main", 116
  characters long, and it carries `Reviewed-on:` and `Reviewed-by:` lines.
- The merge's Build refused that commit in the step *The pushed commits' messages*. The subject was too long, two
  lines were not trailers, and it said who. So *Publish* did not run.
- porelo-parent's merge commit `9e9e150` has the same shape. It published only because porelo-parent's Build has no
  push-commit step.
- The merge offers every style today. The forge role sets none, and the repositories come from the migration with
  Forgejo's defaults.

## Plan

- **One style per repository:** `roles/forge/tasks/protection.yml` gains a task before the branch protection, over
  the same `forge_repositories`, through the admin's API (`PATCH /repos/{owner}/{repo}`). It sets:
  - `allow_fast_forward_only_merge: true`, `default_merge_style: fast-forward-only`;
  - `allow_merge_commits`, `allow_rebase`, `allow_rebase_explicit`, `allow_squash_merge` and
    `allow_manual_merge` all `false`.
  - Forgejo 17.0.0 takes `allow_manual_merge` but leaves it out of the repository's answer (measured on a
    throwaway Forgejo 17.0.0). So it is sent and not read back; the six others are.

  *Rebase* is not kept: Forgejo rewrites the committer when it rebases. The task reads the repository back and fails
  unless every field matches, as the branch protection's task does. It reports `changed` only when it patched.
- **The central work after a refused gathered push** ([HO32](README.md#ho32)) arrives as `central/main`, which has
  diverged from local `main` and cannot be merged by fast-forward. A task joins it on a branch of its own: it starts
  from `central/main` and merges local `main` into it with a commit worded by the shared rule. The person approves
  that pull request, and `main` reaches it by fast-forward. Molecule's `forge_push.yml` does so on `central/take`, and
  `doc/local-forge.md` says it. `porelo-host-push` is unchanged; its refusal already asks for the merge in a task.
- **A pull request behind `main`** cannot be merged fast-forward. Its author brings the branch up to date by a rebase
  of their own and pushes it, as the agents already do before opening one.
- **Molecule** (`extensions/molecule/default`): `verify.yml` reads the migrated repository's settings back through
  the API, every field as above. `tasks/forge_gate.yml` has the person's merge commit refused after the approval,
  then the fast-forward taken, with `main`'s head the probe's own commit. Both are seen red against today's role. `tasks/forge_push.yml` merges its two pull requests
  with `{"Do": "merge"}`, a merge commit, which the setting refuses; both become `{"Do": "fast-forward-only"}`.
- **Docs:** the role's README says that the forge merges fast-forward only, and why. Changelog under *Changed*.

## Acceptance

- Molecule's check, seen red first.
- On a rented host: the merge button offers *Fast-forward only* alone, and a merged pull request leaves `main` at its
  own head commit, the commit's author and signature unchanged.

## To be checked

- Whether the pull request page's *Update branch* button still offers a merge from `main` into the branch. If it
  does, it is the same commit of the forge's own one step earlier. Then it is either switched to rebase
  (`default_update_style`, if Forgejo has it) or left out.

## Decided

- **QH37 (b), the operator, 2026-10-27:** `porelo-host-push` gets no guard of its own against a commit of the forge's
  `operator` identity. The merge style alone keeps such commits out, and the public Build's push step would still
  refuse one.
- **QH38 (a), the operator, 2026-10-27:** fast-forward only stays, and the central work is joined on a branch of its
  own by a task, as above, not by a merge commit of the forge's.
