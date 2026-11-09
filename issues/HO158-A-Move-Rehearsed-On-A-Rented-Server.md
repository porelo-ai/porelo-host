# HO158 — A Move Rehearsed On A Rented Server

**Status:** Implementing.
**Size:** L - a new mode of `build/rehearse-move.sh` that drives a whole move on a real server, failing closed at every
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

- **The mode.** `build/rehearse-move.sh rented <address> --key <file> --machine-file <file> --order-time <UTC>`:
  - it makes and deletes no VM;
  - it reaches root by the given key alone (`IdentitiesOnly`), with the server's host key pinned at the first
    connection;
  - it refuses a server that already holds `/etc/porelo-host`, so it never acts on a host it did not set up.
- **The order of the run:**
  1. **Checks.** `porelo-host-check` first, its `vmx`/`svm` and `/dev/kvm` answer kept. With no KVM, the run goes on
     with the pool off and says so.
  2. **up.** The collection copied and installed, with the given machine file (the test organization's) and
     `porelo_host_kvm` as the check said. up is judged by its lines, as the local rehearsal judges it.
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
  Deleting it in the provider's console stays the operator's.
- **Red first:** the refusal over an existing `/etc/porelo-host`, and the trap that runs `down` on an interrupt, each
  tested against a stand-in server (a local rehearsal VM) before the first rented run.

## Acceptance

- On a local rehearsal VM in the new mode:
  - the run passes end to end against the stand-in organization;
  - a second run on the same VM is refused;
  - an interrupt in the middle leaves `down` run and says so.
- On one rented server, with the operator's word: the report holds a line per step, the server is left with no host,
  and the read keys at central are deleted.

## To be checked

- That `porelo-host-push` takes the central token from a pipe as it does from a terminal.
- Whether the rented servers offer KVM, measured by the run's first step.
