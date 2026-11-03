# HO109 — How Long The Host Has Not Read Its Organization

**Status:** Idea.

**What must be true.** `org status` says when the host last read its organization, so the host admin, and the interface
on their behalf, sees how long it has not. A follow that cannot fetch keeps the state it took, so a removed member keeps
their login for as long as that lasts; today the status says nothing of it, as only a refusal is recorded.

## To be checked

- `isolated_porelo` records only exit 65 as `refused`; any other failure of `org fetch`, such as a forge that cannot be
  reached, leaves nothing `org status` reads. `applied.json` is written at each state taken, and whether its time is
  enough or the follow keeps a time of its own, as a refused state does not rewrite it either.
- Whether a person, not only root, should read this, as `org status` is root's alone.
