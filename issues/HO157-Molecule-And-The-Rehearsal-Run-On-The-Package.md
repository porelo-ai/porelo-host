# HO157 — Molecule And The Rehearsal Run On The Package

```json
{
  "$schema": "issue-1.json",
  "id": "HO157",
  "title": "Molecule And The Rehearsal Run On The Package",
  "state": "Review",
  "size": "M",
  "priority": "Medium",
  "rank": 2,
  "blockedBy": [],
  "covers": "Molecule and the move rehearsal install the local `porelo-host` package and check its version; `porelo-vm` moves to `build/`."
}
```

**Why this size.** `build/molecule.sh`, `build/rehearse-move.sh` and Molecule's acts change to install and call the
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
  purges removed people only after seven days. Forge setup and upgrade refuse their missing socket push judge before
  changes.
- The collection installs and mounts the pre-receive hook at /usr/local/libexec/porelo/pre-receive; the package only
  links each repository there. Seed configuration and base-volume upload remain collection tasks.
- The four code-review findings have red reproductions and passing fixes: SSH argument preservation, existing admin
  access, fresh repository metadata and separate remote package sets. No second reading of their fixes is needed.
- The forge's refusal of a missing socket push judge is gone since snapshot 462 brings the judge. The real host runs
  are recorded below; `rented` preparation runs in the rehearsal on a rented server.
- No host install task names `porelo-vm`: in `roles/` and Molecule's acts it stands only in the legacy-program
  removal and its absence check, and `roles/vm_pool/README.md` says it is never installed.
- The native wiring review found upgrade cleanup before the remaining forge refusal, expected refusal statuses counted
  as failures, and fixture installation outside restoration. Each has a red reproduction and a passing focused fix.
- `build/rehearse-move.sh start` and `down` on Core's local hand-over of porelo b7c5f2de5
  (`0.5.1~snapshot.461+local.20261110T084038`), on this machine's libvirt with Molecule's stand-in organization: up
  passes; on the VM no former script, no `porelo-vm` and no `/usr/local/libexec/porelo-host*` is installed, and the
  host's units run `/usr/sbin/porelo-host` (judge-push behind its socket, org follow, task sweep). The move's host check
  passes its host program line against the pinned build; its task lines need a person and a task, which the stand-in
  has not, and stay for the operator's test. The host's down passes and the VM is deleted.
- The pool scenario on the test host, on Core's hand-over of porelo b7c5f2de5 with porelo-machines' runtime JARs from
  porelo-buildtools 45b4279: syntax, converge, idempotence and verify pass, the pool's rental and revert among them.
  side_effect stopped at down on hostadmin's host-admin membership, which down no longer counts since
  [HO156](README.md#ho156)'s last fix.
- The pool scenario on the test host again, on f648620 with the pinned published packages of snapshot 462 (as
  `build/fetch-host-deb.sh` gives them) and the same runtime JARs: syntax, converge, idempotence, verify and
  side_effect pass, down among them, and the run's VM, disk and seed are removed.
- The default scenario on the test host, on the pinned published packages of snapshot 462, with
  [HO156](README.md#ho156)'s fix to down (afc4391): forge off (run 15c) and forge on (run 15a), syntax, converge,
  idempotence, verify and side_effect pass, the package's version and legacy-program absence checks among them, and
  each run's VM, disk and seed are removed. The run before the fix stopped at down on the host-admin membership.
