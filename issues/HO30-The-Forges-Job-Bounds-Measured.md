# HO30 — The Forge's Job Bounds Measured

**Status:** Idea.

**What must be true.** What the forge's roles promise and Molecule reads only from the files they write is also seen
in the running system: a job's container carries its bounds.

The forge has no CA for Porelo to pick up: its gate without TLS replaced it.

## To be checked

- That a job container the runner starts takes `--cpus`, `--memory` and `--pids-limit` from `container.options` under
  rootless podman, read with `podman inspect` of a running job; Molecule reads them from the runner's configuration.
