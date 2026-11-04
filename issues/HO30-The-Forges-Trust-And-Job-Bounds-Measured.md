# HO30 — The Forge's Trust And Job Bounds Measured

**Status:** Idea.

**What must be true.** What the forge's roles promise and Molecule reads only from the files they write is also seen
in the running system: a job's container carries its bounds, and Porelo picks up the forge's CA when a task starts.

## To be checked

- That a job container the runner starts takes `--cpus`, `--memory` and `--pids-limit` from `container.options` under
  rootless podman, read with `podman inspect` of a running job; Molecule reads them from the runner's configuration.
- Whether Porelo reads `porelo/ca-certificates.pem` in the config folder at each task start or once per `vault serve` (a running
  vault after `up`). The forge has no CA of its own today: it stands behind its gate without TLS, and the role removes
  the old one, so this point has nothing to read while that holds.
