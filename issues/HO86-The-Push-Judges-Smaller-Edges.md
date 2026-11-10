# HO86 — The Push Judge's Smaller Edges

```json
{
  "$schema": "issue-1.json",
  "id": "HO86",
  "title": "The Push Judge's Smaller Edges",
  "state": "Idea",
  "size": "-",
  "priority": "Medium",
  "rank": 18,
  "blockedBy": ["HO85"],
  "covers": "The push judge's smaller edges from its reading, gathered: links in the arming, the removal's checks, a first-push race, the null object, the answer's field and record checks pinned by tests."
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

## Not taken in

- `core.hooksPath` read without `--includes`, or relative to another directory than the one Git resolves it in, and
  an arming that finds no repositories directory although arrivals were recorded: each needs the forge account, or
  its container's root, to write a repository's config, Forgejo's `.gitconfig` or the volume's layout. That account
  can remove the hook outright, so the judge does not guard against it, and an arming check cannot either.
