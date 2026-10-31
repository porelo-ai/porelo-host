# HO63 — Podman Reached Through The Account's Session Bus

**Status:** Review (Backlog: operator, 2026-10-31).
**Size:** S.
**Blocked by:** -.

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

## Plan

- `porelo-host-person` (`as_account`, every call as `porelo-forge` or `porelo-matrix`) and `porelo-host-project`
  (`forge_command`) pass `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/<uid>/bus` beside `XDG_RUNTIME_DIR`, and refuse
  with 69, naming the account, when that path is no socket.
- The roles' environments (forge, runner, the person's own forge play, matrix, porelo) name the bus beside the runtime;
  the shell tasks already did. Forge's accounts and Matrix's account wait up to 60 s for their bus after linger and
  fail naming the account.

## Tests

- `tests/unit/roles/test_session_bus.py`: every runtime the roles set names its bus; the waits come before the first
  task with an account environment; the project helper refuses a missing bus or a plain file in its place.
- `tests/unit/roles/test_porelo_host_person_services.py`: a service account without its bus is refused by name before
  any command; a call names its runtime and its bus.

## Acceptance

- [ ] On walk6m (Ubuntu 26.04) a fresh `up` passes, and `podman info` as `porelo-forge` names the systemd cgroup
  manager.
- [ ] With the forge account's user manager stopped, `porelo-host-person forge-token` refuses naming `porelo-forge`
  instead of crun's cgroup error.
