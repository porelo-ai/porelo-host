# HO132 — A Move Rehearsed On A Local VM

```json
{
  "$schema": "issue-1.json",
  "id": "HO132",
  "title": "A Move Rehearsed On A Local VM",
  "state": "Review",
  "size": "S",
  "priority": "Medium",
  "rank": 21,
  "blockedBy": [],
  "covers": "`build/rehearse-move.sh` makes a throwaway VM, runs `up` with the forge and no pool, opens the room tunnel and takes it all down again, so a move is rehearsed before a host is rented."
}
```

**Why this size.** one shell script beside `build/molecule.sh`, on the same VM code, and its trial on this kind of machine up to
an empty `up` and a clean `down`.

**What must be true.** Before a host is rented, an agent's move can be rehearsed on a throwaway VM on a development
machine with libvirt. One command makes the VM and runs `up` with the forge on and no pool, another opens the room's
tunnel to it, and `down` leaves nothing behind. The organization is Molecule's stand-in unless a machine file for a real
one is given explicitly, so nothing outside is touched by default.

## Plan

- `build/rehearse-move.sh` with four verbs:
  - `start [--machine-file <file>]`: refuse an earlier run's leftovers, make the VM from `build/test-image` by
    `porelo-vm` (8 vCPUs, 16 GiB, a 80 GiB disk), install the collection built from this checkout, write the inventory
    (forge on, no pool, no KVM asked), and run `up` on the VM. Without `--machine-file`, it writes the stand-in
    organization's machine file, as Molecule's converge does.
  - `ssh [<command>]`: the VM's admin login, with the run's own key and host key.
  - `tunnel <login> <port>`: `build/room-tunnel.sh` to the VM, with the run's host key.
  - `down`: `down` on the VM, then the VM, its disk and its seed deleted, believed only as libvirt lists none of
    them, and the run's directory removed. A real organization keeps the host's read keys on its repositories, as for
    any host, until their owner removes them.
- `porelo-vm make` takes its disk size from `PORELO_VM_DISK`, default today's `20G`, so the pool and Molecule are unchanged.
- An interrupt or a failed `start` deletes the VM it made.
- `AGENTS.md` names the script among the files that cannot be Java.

## Acceptance

- `start` on this machine reaches an `up` that ends with no failed and no waiting step, and `down` leaves libvirt listing
  nothing of the run. Both are observed, not taken from exit codes.
- A second `start` over a left VM is refused and names it.

## Declined from the reading

- The seed ISO holding the VM's host key stays in libvirt's pool until `down`, as `build/molecule.sh`'s does: the key is a
  throwaway VM's, made for the run on this machine, and goes with the VM.
- The collection's tarball is built by `build/tools.sh`, which mounts the whole checkout, the run's keys under `target/`
  included, into the pinned tools image as the calling account; it is the same account's own files.

## To be checked

- The tunnel needs a person admitted on the VM, which an empty `up` has not; its verb is tried at the rehearsal.
