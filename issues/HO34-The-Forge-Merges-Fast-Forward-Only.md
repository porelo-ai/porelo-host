# HO34 — The Forge Merges Fast-Forward Only

**Status:** Estimated by the operator on 2026-10-27.
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

  *Rebase* is not kept: Forgejo rewrites the committer when it rebases. The task reads the repository back and fails
  unless every field matches, as the branch protection's task does. It reports `changed` only when it patched.
- **A pull request behind `main`** cannot be merged fast-forward. Its author brings the branch up to date by a rebase
  of their own and pushes it, as the agents already do before opening one.
- **Molecule** (`extensions/molecule/default`): the migrated repository's settings read back through the API, every
  field as above. The check is seen red against today's role.
- **Docs:** the role's README says that the forge merges fast-forward only, and why. Changelog under *Changed*.

## Acceptance

- Molecule's check, seen red first.
- On a rented host: the merge button offers *Fast-forward only* alone, and a merged pull request leaves `main` at its
  own head commit, the commit's author and signature unchanged.

## To be checked

- Forgejo 17.0.0's field names in `PATCH /repos/{owner}/{repo}` for the fast-forward style and the default. The
  names above are from Gitea's API since 1.21, not yet run against this forge.
- Whether the pull request page's *Update branch* button still offers a merge from `main` into the branch. If it
  does, it is the same commit of the forge's own one step earlier. Then it is either switched to rebase
  (`default_update_style`, if Forgejo has it) or left out.

## Decided

- **QH37 (b), the operator, 2026-10-27:** `porelo-host-push` gets no guard of its own against a commit of the forge's
  `operator` identity. The merge style alone keeps such commits out, and the public Build's push step would still
  refuse one.
