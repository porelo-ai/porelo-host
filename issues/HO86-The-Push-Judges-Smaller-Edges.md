# HO86 — The Push Judge's Smaller Edges

```json
{
  "$schema": "issue-1.json",
  "id": "HO86",
  "title": "The Push Judge's Smaller Edges",
  "state": "Analyzed",
  "size": "-",
  "priority": "Medium",
  "rank": 18,
  "blockedBy": ["HO85"],
  "covers": "The push judge's smaller edges from its reading, gathered: links in the arming, the removal's checks, a first-push race, the null object, the answer's field and record checks pinned by tests.",
  "openQuestions": 1
}
```

**What must be true.** The smaller edges a reading of the push judge found are closed, each with a test seen red then
green:

- the arming stops on a linked repository or a linked `git` directory instead of passing over it, requires the
  mounted hook and the link's target to be executable plain files before linking, and leaves no link behind when it
  stops;
- a project's removal checks the arrivals directory itself root's alone and decides once whether there is anything to
  remove, so a later look cannot remove through a link;
- two first pushes of a project, side by side, both make or find its arrivals directory, neither answered 500;
- a verdict never records Git's null object name as a commit, and the stand-in judges no deleted ref;
- each field check of Porelo's answer is pinned by a case that fails it alone (time without `Z`, a commit that is no
  string, no signer, a signer without a fingerprint);
- each mode, link and unknown-entry check of the arrivals and of the forge's repositories directory is pinned by a
  case, and the texts claim no more than the tests show.

## Plan

Read in porelo-host 8133028 and porelo c43062468. The push judge, its arming and the project's removal are no longer in
this repository: since d316ca7 the collection runs `porelo-host judge-push` from porelo's package (B549, Review), and
only the hook `roles/forge/files/porelo-forge-pre-receive` is left here, which none of these edges touches. Each edge
read against porelo's `host/` module:

- **Arming.** Still open as written: the arming script in porelo's
  `host/src/main/java/org/fuin/porelo/host/FollowPushes.java` passes over a linked repository (`continue`), checks the
  mounted hook and the link's target with `-f` and `-x`, which follow links, and leaves a link it has just made behind
  when the target then fails `-x`.
- **Removal.** Partly open: `ProjectRegistration` removes the arrivals through `ProjectArrivals.removeProject` and then
  looks again (`files.exists`, then `files.delete`); whether the second look can follow a link is for porelo's host to
  show.
- **First push race.** Closed: `HostFiles.directories` takes a directory another push made first and checks it again.
- **Null object, field checks, record checks.** Each malformed field of the worker's answer has its own case in
  `PushJudgementTest` (B549's as built); whether a verdict can record Git's null object name for a push that mixes a
  deletion with an update is to be checked there.

Nothing of this issue is built in porelo-host. The open edges, the arming's three and the two to be checked, are a small
issue for porelo's `host/` module (S, about 27 min), with each case seen red first in its `HostPush` and `FollowPushes`
tests.

## Open questions

- **Where it goes.** My proposal: Agent Core files the open edges as an issue of porelo, waiting for B549, and this issue
  becomes Rejected with that issue named as its successor.

## Not taken in

- `core.hooksPath` read without `--includes`, or relative to another directory than the one Git resolves it in, and
  an arming that finds no repositories directory although arrivals were recorded: each needs the forge account, or
  its container's root, to write a repository's config, Forgejo's `.gitconfig` or the volume's layout. That account
  can remove the hook outright, so the judge does not guard against it, and an arming check cannot either.
