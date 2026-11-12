# HO178 — The Rented Rehearsal Turns The Pool On

```json
{
  "$schema": "issue-1.json",
  "id": "HO178",
  "title": "The Rented Rehearsal Turns The Pool On",
  "state": "Review",
  "size": "S",
  "priority": "High",
  "rank": 2,
  "blockedBy": [],
  "covers": "`build/rehearse-move.sh rented` takes the VM pool's systems and accounts and the forge's job capacity, writes them into the host's inventory and the check's choices, so a rented KVM host stands with the forge and the pool for another repository's pool proofs."
}
```

**Why this size.** a few lines in the inventory `rented` writes and in its check's choices, with the options that feed
them, and the rehearsal's own test of the inventory.

**What must be true.** `rented` with `--pool ubuntu,fedora --pool-accounts 2 --jobs 4` writes `porelo_host_vm_pool`
with those systems and accounts and `forge_runner_capacity: 4` into the inventory it sends, asks the check for KVM and
that pool so a host that cannot hold them is refused before `up`, and without the options writes what it writes today.
A host held with `PORELO_REHEARSAL_HOLD_FILE` then stands with the forge and the pool until the hold file is removed.

**Why.** Agent Smith's pool proofs of CC40, PI40, AG05 and OM37 run on one rented KVM host on 2026-11-13. Today the
inventory `rented` writes (build/rehearse-move.sh, `prepare_host`) holds the forge and KVM but no pool, and its check
asks for no KVM, so the only documented way to set up a rented host cannot give that host its pool. Filed on the
coordinator's order to prepare the rental.

## Acceptance

- The rehearsal's inventory, written by `rented` with and without the pool options, holds exactly the settings above;
  shellcheck and the YAML check pass.
- The rental's `up` reports the pool's VMs made and `/etc/porelo-host/pool/pool.json` present.

## As built

- `rented` takes `--pool`, `--pool-accounts` and `--jobs`, refuses anything else before any ssh, writes
  `porelo_host_vm_pool` and `forge_runner_capacity` into the inventory, and asks the check for KVM, the pool and the
  jobs. A held run keeps them for its resume. `doc/testing.md` names the options.
- tests/unit/test_move_tools.py proves the choices, the inventory with and without the options, and nine refusals;
  the inventory and the list's shape each went red with their rule removed. The rental's own `up` is the remaining
  proof, tomorrow.
