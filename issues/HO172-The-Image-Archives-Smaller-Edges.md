# HO172 — The Image Archives' Smaller Edges

```json
{
  "$schema": "issue-1.json",
  "id": "HO172",
  "title": "The Image Archives' Smaller Edges",
  "state": "Idea",
  "size": "-",
  "priority": "Low",
  "rank": 99,
  "blockedBy": [],
  "covers": "The forge image archives' smaller edges from their reading, gathered: what an interrupted load leaves, a named directory that is missing, check mode, the archive tests' fixtures, and build/molecule.sh's checks and clean-up."
}
```

**What must be true.** The forge role's archive load and `build/molecule.sh` close these edges, none of which can do
harm as the rules define it:

- An `up` killed during the copy or the load leaves `/var/tmp/porelo-forge-image.*` and skopeo's unpacked archive in
  `/tmp`; `down` or the next `up` removes them, or skopeo's `TMPDIR` is the role's own directory.
- A `forge_image_archives` that does not exist, or is no directory, stops `up` instead of pulling every image.
- In check mode the load says it would load an image instead of reporting the pull.
- The archive tests' fixture holds the index blob a real archive holds; the refusals of a non-absolute directory, an
  unpinned reference and a non-regular archive have tests.
- A malformed `index.json` stops with the role's own message, not a template error.
- `build/molecule.sh` refuses a `PORELO_HOST_IMAGES` that is a symlink or empty, copies only the `<digest>.tar` files
  it checked, removes a partial cloud image after a failed download, and traps an interrupt from its start.
