# HO14 — The Collection's Python Under `ansible-test sanity`

**Status:** Backlog.
**Size:** S - one pinned container image and one Build step; the findings it brings are fixed where they arise.

**What must be true.** The collection's Python, the `lines` callback, passes `ansible-test sanity` in the Build, with
everything it runs pinned, so a plugin's documentation is checked against its code as Galaxy's own import checks would.

## Plan

- An image of its own beside the Ansible tools image, its Python requirements for sanity installed at build time by
  hash, pinned by digest in `build/`.
- A Build step that runs `ansible-test sanity --docker <that image>` or, if `--docker` will not take a local image,
  inside it with `--python` set; no requirement fetched at run time.
- `doc/decisions.md`'s `ansible-test sanity` entry says what then holds.
