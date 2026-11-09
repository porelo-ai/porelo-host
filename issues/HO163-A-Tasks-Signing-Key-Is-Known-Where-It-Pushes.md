# HO163 — A Task's Signing Key Is Known Where It Pushes

**Status:** Backlog.

**What must be true.** A task's signed commits show as verified on the host's forge, since the key a task signs with is
registered with the forge account that receives its push, and the same commits brought to the central forge do not
read as signed by an unknown key there.

## Acceptance

- On the host's forge, a task's commit shows a verified signature of the task's account; a commit signed by any other
  key does not.
- What the central forge can be told of a task's key, and what it cannot (a certified key the central forge does not
  take), is measured and written down before anything is built for it.
