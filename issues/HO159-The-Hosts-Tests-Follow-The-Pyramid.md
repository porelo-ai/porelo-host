# HO159 — The Host's Tests Follow The Pyramid

```json
{
  "$schema": "issue-1.json",
  "id": "HO159",
  "title": "The Host's Tests Follow The Pyramid",
  "state": "Analyzed",
  "size": "L",
  "priority": "Medium",
  "rank": 1,
  "blockedBy": [],
  "covers": "The host's tests follow the pyramid (ST296): its pool and role logic unit-tested over fakes, its subprocess tests narrowed, `tests/unit` and `tests/integration` apart, and Molecule's sleeps gone.",
  "openQuestions": 1
}
```

**Why this size.** eight fixes in this repository, each S or XS, sized below; they come one after another, not as one change.

**What must be true.** porelo-host's tests follow the test pyramid as AGENTS.md "Testing and machines" and
porelo-project's `doc/test-pyramid.md` set it out (story ST296). Each flow of a role or a build script is plain logic
behind a small seam, proven by unit tests over fakes that run in milliseconds. Integration tests run a real tool
(`ansible-playbook`, `ssh-keygen`, `sshd -T`, `git`, a socket) narrowly on that core. Molecule and the rehearsals
cover only what a lower level cannot show: systemd, the kernel, SSH, podman, libvirt.

## Where the tests stand

The audit was done on 2026-11-09 against main and against [HO156](README.md#ho156)'s build on it, which removes the
Python host scripts.

**Before [HO156](README.md#ho156)** (main), counted by an agy reading:

| Level | Count | Share |
|---|---|---|
| Unit | 687 cases | 38 % |
| Integration | 1,109 cases | 62 % |
| VM | 3 suites | - |

- **Integration** means a subprocess, `ansible-playbook`, `ssh-keygen`, `git`, a PTY or a socket.
- **The VM suites** are the Molecule default scenario, the Molecule measure scenario and the two-VM move rehearsal.
- Most of the integration tests are the Python host scripts' own: person, project, push, stop, forge-token,
  forge-gate and pool-revert, about 4,200 `git` and 3,850 `ssh-keygen` calls. [HO156](README.md#ho156) deletes those
  scripts and their tests. The flows move to `porelo-host`, which porelo builds and tests (Agent Core's audit).

**After [HO156](README.md#ho156)** (`tests/unit`, measured by pytest's own times in the tools image, 2:50 min for 322
tests):

| Level | Count | Share by count | Time | Share by time |
|---|---|---|---|---|
| Unit (under 50 ms each) | 198 | 61 % | 1.7 s | 1 % |
| Integration (50 ms or more) | 124 | 39 % | 133.9 s | 99 % |
| Molecule default (VM) | 1 scenario | - | not yet green on [HO156](README.md#ho156); 4:13 min up to the install step | - |
| Move rehearsal (two VMs) | 1 | - | not measured today | - |

- **Molecule default** has 233 Ansible tasks, 64 of them asserts, and 108 checks in `follow_act.py`.
- **The rented-machine suite** is `build/rehearse-move.sh rented`. Its phase-1 runs on 2026-11-09 took 2 to 6
  min each.
- **The shares miss the rule.** Unit is 61 % by count where the rule asks 70–80 %. Nearly all the time goes to
  integration. The VM runs stand at one scenario and one rehearsal, which is about right.

## Flows proven only through an integration or a VM run

- **`plugins/callback/lines.py`**, the line output of `up` and `down`. It is tested only through 29 `ansible-playbook`
  runs in `test_lines.py`.
- **`build/move-check.sh`**, the five verdict rules of a move. It is tested only through 46 shell, Python and awk runs
  in `test_move_tools.py`.
- **`porelo-host-check`**, its package lock and reachability timeout. It is tested through 29 `python3` subprocesses
  in `test_porelo_host_check.py`, with more than 5 s of real `time.sleep`.
- **`roles/vm_pool`**:
  - which systems and accounts are valid, and the checksum manifest;
  - pruning stale VMs and the memory bounds;
  - rendering `pool.json` and the cloud-config.

  These are tested only in Molecule with `PORELO_HOST_MOLECULE_POOL=on`, which GitHub's runner never sets.
- **Role logic in Jinja expressions**, tested only by `ansible-playbook` subprocesses or Molecule:
  - `base` (host, firewall, controllers, kvm), with the route and address extraction and the nftables rendering;
  - `forge` (accounts, admin, settings);
  - `porelo` (needs, setup, organization);
  - `playbooks/up.yml` and `down.yml`.
- **The capacity, CPU, firewall, admin-key and people checks**, which run 29 `ansible-playbook` subprocesses across
  `test_forge_capacity.py`, `test_base_cpu.py`, `test_base_down_firewall.py`, `test_base_admin_key.py` and
  `test_down_people.py`.

## Tests that wait or need a real tool where a fake would do

- **`extensions/molecule/default/files/PoolAcceptance.java:42`** sleeps 2 minutes to let the pool VM's clock run.
- **`extensions/molecule/default/side_effect.yml:20-45`** waits 30 s for the dpkg lock a second time, testing again
  what `porelo-host-check --wait-packages` already proves in `tests/unit`.
- **`tests/unit/roles/test_porelo_host_check.py`** waits more than 5 s through `package_lock_after` and the
  `reaches` timeout, with no injected clock.
- **`tests/unit/plugins/callback/test_lines.py`** starts `ansible-playbook` 29 times where the callback's event
  handlers could be called directly.

## Fixes, by value

1. **S: unit-test `roles/vm_pool` in Python.**
   - What: the validation, the memory bounds, the manifest match, the prune rule and the two templates.
   - Why first: it closes the largest blind spot. GitHub's runner never runs the pool, so today these flows are seen
     only on a developer's VM.
2. **S: unit-test the role logic in Jinja expressions.** This covers `base` (route, address, nftables, controllers),
   `forge` (accounts, admin, settings), `porelo` (needs, setup, organization) and the two playbooks. The expressions
   are rendered with Ansible's templar over fake facts, so a fault in them shows in milliseconds rather than in
   Molecule.
3. **S: call `plugins/callback/lines.py`'s handlers directly with fake events.** One `ansible-playbook` contract test
   stays. This saves 28 subprocess runs.
4. **XS: inject a clock and a pause into `porelo-host-check`.** Its tests then load the module rather than starting
   it, which saves more than 5 s of sleep and 29 subprocesses.
5. **S: turn `build/move-check.sh` into Python behind a `HostProbe` seam.** The five verdict rules are then tested
   in-process over fake probes.
6. **S: test the capacity, CPU, firewall, admin-key and people expressions in Python.** One `ansible-playbook` test
   stays per role, so 29 subprocesses become 5. `converge.yml`'s duplicate failing `up` runs, at lines 166–205, and
   `tasks/capacity_refused.yml` go, since the unit tests show the refusals.
7. **XS: drop the 2-minute sleep from `PoolAcceptance.java` and the second dpkg-lock wait from `side_effect.yml`.**
   The pool VM's clock is set back over SSH before give-back instead. This saves 2.5 min on every pool run.
8. **S: split `tests/unit` into `tests/unit` and `tests/integration`.**
   - `tests/unit` has no subprocess and no socket, with a target of under 5 s.
   - `tests/integration` holds the real `ansible-playbook`, `ssh-keygen`, `sshd -T` and `git` tests.
   - `build/tools.sh` runs them as two steps, unit first.
   - The Build refuses a subprocess or a socket in `tests/unit`, through a guard in `conftest.py`.

## Plan

Read in porelo-host 8133028 against the audit above:

- **Today's unit run.** `tests/unit` holds 484 tests: 483 passed and 1 skipped (`test_person_ssh`, no `sshd` in the
  tools image), in 282.6 s in the tools image (measured 2026-11-12), against 2:50 min for 322 when audited; the
  rehearsal's tests in `test_move_tools.py` grew with the rented mode. The split of fix 8 matters more than when
  audited.
- **Still as audited.** `PoolAcceptance.java:42` still sleeps two minutes; `build/move-check.sh` and
  `plugins/callback/lines.py` stand as audited; the role tests under `tests/unit/roles` still run `ansible-playbook`.
- **Order and size.** Fixes 1 (S), 2 (S), 3 (S), 4 (XS), 5 (S), 6 (S), 7 (XS) and 8 (S), with fix 8 first, so every
  later fix lands in the right half; about 200 min at the medians (S 27, XS 8), so L.
- **Tests that go red first:** fix 8's `conftest.py` guard refuses a test in `tests/unit` that starts a process, seen
  red first; for fixes 1, 2, 4 and 6 each rule's unit test is seen red with the rule removed; fixes 3, 5 and 7 move
  existing tests and keep them green.
- **Files that cannot be Java.** Fix 5 turns `build/move-check.sh` into Python; this repository's list of such files
  in `AGENTS.md` changes with it.

## Open questions

- **One issue, or one per fix?** My proposal: one issue built in this order, each fix its own commit, handed over
  after fixes 8, 1 and 2 (the split and the largest blind spots) and again at the end.

## Acceptance

- **The shares:** unit at 70–80 % by count in `tests/unit` and `tests/integration` together, with `tests/unit` under
  5 s in the tools image.
- **The pool:** every rule of `roles/vm_pool` that Molecule's pool scenario exercises has a unit test. Each one was
  seen red with the rule removed.
- **The sleeps:** none in `PoolAcceptance.java` or in a unit test.
- **The guard:** `tests/unit`'s guard refuses a test that starts a process. The guard itself was seen red first.

## Why

The operator called the pyramid very important, and ST296 asks every repository to follow it. Today a fault in a
role's expression or a pool rule shows first in a Molecule run on a VM, or on the operator's machine. Molecule's
default run is red twice today for a version pin that a unit test of the role's defaults could have caught.
