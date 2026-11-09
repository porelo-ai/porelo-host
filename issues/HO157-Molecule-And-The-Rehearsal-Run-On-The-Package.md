# HO157 — Molecule And The Rehearsal Run On The Package

**Status:** Implementing.
**Size:** M - `build/molecule.sh`, `build/rehearse-move.sh` and Molecule's acts change to install and call the
package; `porelo-vm` moves to `build/`.

**What must be true.** Molecule's scenarios and the move rehearsal set a VM up with the `porelo-host` package built
on the development machine. They read its version, and they exercise its verbs where the scripts were called. The VM
they run on is still made by `porelo-vm`, a development tool that is no longer installed on any host.

## Plan

- **`porelo-vm`** moves from `roles/vm_pool/files/` to `build/`. `build/molecule.sh` and `build/rehearse-move.sh`
  take it from there; its tests (`tests/unit/test_move_tools.py`) follow it.
- **The local package.** `build/molecule.sh` copies the local `porelo-host` `.deb` with porelo's, by the same packages
  path it uses today, and `up` installs it from there. The rehearsal does the same.
- **What changes in Molecule:**
  - its acts (`follow_act.py` and the verify tasks) call `porelo-host` and `porelo host` verbs where they called the
    scripts;
  - its verify reads `porelo-host --version` against the pinned version;
  - the pool scenario (`PORELO_HOST_MOLECULE_POOL=on`) is the one that exercises `porelo-host pool …`.
- **The move's host check** reads `porelo-host --version` instead of grepping each script for an issue's line.
- **Red first.** Molecule's verify asserts the pinned version and that none of the removed scripts is on the VM. It
  fails against today's collection.

## Acceptance

- Molecule's default and pool scenarios green on the package, with the version and absence checks seen red first.
- `build/rehearse-move.sh start` and `down` on the package, and the move's host check passing against it.
- No host install task names `porelo-vm`.
