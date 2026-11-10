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
  `PORELO_HOST_DEB` selects that archive, `PORELO_HOST_PACKAGES` supplies the existing local package directory, and
  `build/stage-packages.sh` refuses conflicting identities and multiline metadata before staging a fresh set.
  Package and executable versions use the exact Debian build version; the collection version remains separate.
- **Existing rentals.** `build/rehearse-move.sh rented <login@host> <known_hosts> [--machine-file <file>]` prepares an
  already leased host, never creating or deleting its lease. `PORELO_HOST_ADMIN_KEY` names the intended public admin
  key. It shares the VM's preparation, keeps existing SSH keys, and installs from a manifest-specific package directory.
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

## To be checked

- `porelo-vm` and the development callers use `build/`; the rehearsal fixture follows that path.
- Local package staging, pre-up copying and installation, exact version verification, removed-program absence and
  the move's executable version check have unit coverage, seen red before implementation.
- Follow, gate and pool wiring uses the native package. Its command names are forge gate and pool make, address and
  delete. Runtime restoration uses org follow. Manual purge and desktop interaction have no package verb; the follow
  purges removed people only after seven days. Forge setup and upgrade refuse their missing socket push judge before changes.
- The collection installs and mounts the pre-receive hook at /usr/local/libexec/porelo/pre-receive; the package only
  links each repository there. Seed configuration and base-volume upload remain collection tasks.
- The four code-review findings have red reproductions and passing fixes: SSH argument preservation, existing admin
  access, fresh repository metadata and separate remote package sets. No second reading of their fixes is needed.
- The default and pool scenarios, non-bare VM start and rented preparation still need real host runs. Forge setup
  still refuses the package's missing socket push judge; a stopped converge is not acceptance.
- The native wiring review found upgrade cleanup before the remaining forge refusal, expected refusal statuses counted
  as failures, and fixture installation outside restoration. Each has a red reproduction and a passing focused fix.
