# HO14 — The Collection's Python Under `ansible-test sanity`

```json
{
  "$schema": "issue-1.json",
  "id": "HO14",
  "title": "The Collection's Python Under `ansible-test sanity`",
  "state": "Review",
  "size": "S",
  "priority": "Medium",
  "rank": 34,
  "blockedBy": [],
  "covers": "`ansible-test sanity` on the whole collection in the Build, offline, its requirements taken by hash."
}
```

**Why this size.** one pinned container image and one Build step; the findings it brings are fixed where they arise.

**What must be true.** The whole collection, its Python with the `lines` callback, passes `ansible-test sanity` in the Build, with
everything it runs pinned, so a plugin's documentation is checked against its code as Galaxy's own import checks would.

## Plan

- An image built from the tools image `build/tools-image` pins, by `build/sanity/Containerfile`: sanity's wheels and
  pip's bootstrap script, each taken by its hash from `build/sanity/requirements.txt` and the Containerfile, and pip
  configured to take nothing else.
- `build/sanity.sh` runs `ansible-test sanity` in it on a copy of the files git holds, with no network, in the Build
  and locally; what it leaves standing is named with its reason in `tests/sanity/ignore-2.21.txt`.
- `doc/decisions.md`'s `ansible-test sanity` entry says what then holds.
