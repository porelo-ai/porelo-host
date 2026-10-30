# HO63 — Podman Reached Through The Account's Session Bus

**Status:** Idea.

**What must be true.** Every `podman` call the roles and helpers make as a service account (`porelo-forge`,
`porelo-runner`, `porelo-matrix`) reaches that account's systemd user manager, so podman uses the systemd cgroup
manager and never falls back to cgroupfs. A missing bus refuses loudly, naming the account, instead of crun's cgroup
error.

## Why

Walk 23 on a rented Ubuntu 26.04.1 host: `runuser -u porelo-forge -- env XDG_RUNTIME_DIR=... podman exec forgejo ...`
failed with `crun: ... cgroup.procs: Permission denied: OCI permission denied`; with
`DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/<uid>/bus` added it worked. The walk's `on_forge` was patched by hand.
The roles (forge, matrix) and the helpers (`porelo-host-person`, `porelo-host-forge-password`, `porelo-host-project`,
`porelo-host-push`) set only `XDG_RUNTIME_DIR` the same way.

## To be checked

- Why Molecule's Ubuntu 26.04 VM is green without the variable: whether `/run/user/<uid>/bus` exists on the rented host
  and which cgroup manager `podman info` names there with and without it.
- One place per language that gives the environment, so no call is missed.
