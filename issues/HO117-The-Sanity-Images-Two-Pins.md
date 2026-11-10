# HO117 — The Sanity Image's Two Pins

```json
{
  "$schema": "issue-1.json",
  "id": "HO117",
  "title": "The Sanity Image's Two Pins",
  "state": "Idea",
  "size": "-",
  "priority": "Medium",
  "rank": 8,
  "blockedBy": [],
  "covers": "The `pip` and `pylint` the sanity image pins, with open alerts, raised or said why they stay"
}
```

**What must be true.** `build/sanity/requirements.txt` holds no `pip` and no `pylint` with an open alert, or says why one stays, and sanity passes on what it holds.

## Why

Dependabot names seven open alerts on this file, six moderate and one low: six on `pip` 25.2, one on `pylint` 4.0.5. `build` is outside the tarball, so none reaches a host. These tools run in the sanity image, which installs by hash and runs with no network, on the collection's own code.

Neither pin is free to move alone:

- **`pylint` 4.0.5, with `astroid` 4.0.4,** are what `sanity.pylint.txt` of the tools image's ansible-core 2.21.5 asks for, and the file says it is renewed when that image moves.
- **`pip` 25.2** is the pip the image puts into each test's virtual environment, and its bootstrap script `get-pip-25.2.py` is fetched by that name and its hash in `build/sanity/Containerfile` and copied by name in `build/sanity.sh`.

So the first thing to read is whether a newer ansible-core asks for newer ones. The alerts' fixed versions have not been read here: the page wants a login.

## Acceptance

- Each pin raised with its hash, and the bootstrap script with its own, or the reason it stays written in the file's head.
- `build/sanity.sh` passes with the new image, and the Build's sanity with it.
