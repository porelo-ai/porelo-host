# HO158 — A Move Rehearsed On A Rented Server

```json
{
  "$schema": "issue-1.json",
  "id": "HO158",
  "title": "A Move Rehearsed On A Rented Server",
  "state": "Implementing",
  "size": "L",
  "priority": "Medium",
  "rank": 4,
  "blockedBy": [],
  "covers": "The agents run a whole move on a server the operator rented, against a test organization, from `build/rehearse-move.sh`: check, up, vault, follow, forge, pool where KVM is, judge, push and pull, host check, down and read keys, a report per step, and one request to delete the server."
}
```

**Why this size.** a new mode of `build/rehearse-move.sh` that drives a whole move on a real server, failing closed at every
step, and one try on a rented server, which needs the operator's word.

**What must be true.** Once the operator has rented a server and ticked the rehearsals' root key on it, the agents
run a move on it from their development machine by themselves, against a test organization. The run covers the check
before installing, `up`, the vault, the follow, the forge and its Builds, the pool where the server has KVM, the push
judge, the gathered push and pull to central, the host check, and `down` with the read keys taken off central. It ends
with one request to delete the server, and leaves a report of every step.

## Why

Problems of a move show today only in the operator's own test. Most of the host side runs without a person, as the
local rehearsal shows on a VM. On a real server and against a real central forge, it can be run before the operator
spends a test on it.

## Plan

- **The mode.** `build/rehearse-move.sh rented <address> --key <file> [--login <user>] [--machine-file <file>]
  [--order-time <UTC>] [--zone <name>]`:
  - it makes and deletes no VM;
  - it reaches root by the given key alone (`IdentitiesOnly`), with the server's host key pinned at the first
    connection;
  - it refuses a server that already holds `/etc/porelo-host`, so it never acts on a host it did not set up.
  - one root command checks the host and staging paths, exclusively creates staging and writes its owner token;
    an interrupted claim finishes before its exact answer decides ownership; cleanup and every preparation write
    check the token before acting on the server;
  - the given private key must have an Ed25519 public half, checked before connecting; pinning replaces symlinks
    rather than writing through them.
- **The order of the run:**
  1. **Checks.** `porelo-host-check` first, its `vmx`/`svm` and `/dev/kvm` answer kept. With no KVM, the run goes on
     with the pool off and says so.
  2. **up.** The collection copied and installed, with the given machine file (the test organization's) and
     `porelo_host_kvm` as the check said. Its inventory is moved into place immediately before the playbook starts.
     up is judged by its lines, as the local rehearsal judges it.
  3. **The stop.** `porelo-host-stop --stdin vault-new keys` in the test person's account. Its lines come from the test
     identity's vault through a passphrase command, on stdin only.
  4. **The project.** `org refresh` takes the test token on stdin for the first migration. The run waits for the
     follow to carry the project.
  5. **Checks after the follow.** The host check with its project argument; one push to the task's own branch, which
     passes, and one to another branch, which the judge refuses; the runner queue.
  6. **Push and pull.** The gathered push and pull to central, with the test token on stdin.
  7. **down.** The host's `down`, then the read keys found and deleted at central, by the host's name.
- **The hard stop.** The clock starts at the given order time. At 5 h 30 the run goes to `down`, whatever stands.
- **The report.** One directory per run, beside the run's other files, outside the repository. It holds:
  - one line per step, `OK` or `FAIL`, with what was asked and what came back;
  - up's lines;
  - the host check's output;
  - the runner queue;
  - the read keys found and deleted.
- **Fail fast.** A repeated failure stops the run at once and names what repeated. Every exit, an interrupt included,
  runs `down` and the key removal, and names whatever is left.
- **The request to delete.** After `down`, the run's last line names the server, its zone and the time to delete it.
  Deleting it in the provider's console stays the operator's. The run never restores the server: the host's own
  down keeps installed software and its firewall, and only the run's staging directory is removed afterward.
- **Cleanup evidence.** `OK down` requires an actual playbook run with no failed or waiting lines. No inventory
  means `SKIP down`, while a partial inventory still goes through down. The final line distinguishes a check that
  failed before up from an up that never published its inventory, and names packages that may stay. Every remote
  playbook exit still sends its lines; a local SSH failure or timeout starts no further remote reads. Already saved
  report files are replaced only by complete copies.
- **Red first:** the refusal over an existing `/etc/porelo-host`, and the trap that runs `down` on an interrupt, each
  tested against a stand-in server (a local rehearsal VM) before the first rented run.

## Acceptance

- On a local rehearsal VM in the new mode:
  - the run passes end to end against the stand-in organization;
  - a second run on the same VM is refused;
  - an interrupt in the middle leaves `down` run and says so.
- On one rented server, with the operator's word: the report holds a line per step, the host's own down has run,
  its retained software and firewall stay until the server is deleted, and the read keys at central are deleted.

## To be checked

- That `porelo-host-push` takes the central token from a pipe as it does from a terminal.
- (a) on one rented server (Scaleway Elastic Metal, fr-par-1, ordered 2026-11-10 13:16Z, deleted by the operator the
  same day): `build/rehearse-move.sh rented` from main eeb3c08 with the pinned 462 packages and the foo-org machine
  file, as `ubuntu` with sudo, ran 13:31:52Z to 13:36:47Z. `OK` refuse-existing, `OK` check (KVM: CPU flag and
  `/dev/kvm` both there), `OK` up (512 lines, none failed or waiting; up did not stop for a person, since a fresh host
  has none until the follow makes one), `OK` down (no failed or waiting lines); stop, project, judge, push-pull and
  read-keys `SKIP` for phase 2. The last line named the server, its zone and the time to delete it.
- Phase 2, built against the stand-in server in `tests/unit/test_move_tools.py`, each test seen red first: the
  options `--org`, `--person`, `--person-agent`, `--central-token`, `--project` and `--retire-host`, all or none; the
  steps org (retire the old host, add `rented`, its card with the pinned host key, carry), project (`org host refresh`,
  then `org status --json` until the person is active in the project), stop (`stop-secrets --stdin vault-new` from a
  passphrase made for the run, `forge-token`, the central token into the vault on standard input), push-pull (pull,
  push, `central-state --json`), and org-off after down (uncarry, remove; `LEFT in the organization` when it fails).
  Neither secret reaches an argument list, the report or the output. A code reading by another model found a token
  program's failure passing unseen, markers written after a half-done add, the exit of the first failure overwritten
  and ssh offering key files beside the agent; each fixed, with a red test first where the stand-in can show it.
  Known limits: an add that fails having written nothing still asks for a removal, which then says the host may be
  left; a signal while the organization is cleaned up is taken only after it. Not yet run on a rented server.
  The judge step stays `SKIP` until a task's commit is made inside it (`podman exec`, Agent Core 2026-11-10).
- A hold for another run on the same rental (MX99): `PORELO_REHEARSAL_HOLD_FILE` keeps the host up after push-pull
  until the file is removed, and the hard stop still ends it with down; both seen red first against the stand-in.
- (b) phase 2 on one rented server (Scaleway Elastic Metal, fr-par-1, 195.154.103.114, ordered 2026-11-10 16:15Z,
  deleted by the operator the same day): from main 9df8f82 with the 462 packages and `--retire-host machines-foo`, ran
  16:24:34Z to 16:30:23Z. `OK` refuse-existing, check (KVM true), up and org (machines-foo taken off, `rented` added,
  its card filed, foo-project carried); `FAIL` project with exit 69: `org host refresh` logs in as root, and the
  operator's key was not among root's keys (`Permission denied (publickey)`). `OK` down and org-off; no hold, so
  neither MX99 nor [HO165](README.md#ho165)'s measurement ran. Agent Core 2026-11-10: root is refresh's login by design, and the
  operator's key reaching root is part of bringing a host in. The rehearsal now takes `--org-key` and adds that key to
  root's keys at the start of org; seen red first against the stand-in, whose refresh is refused as on the rental
  until the key is there. Refresh also ran `porelo-host-person`, which 462 no longer ships; Agent Core fixes that in
  porelo.
