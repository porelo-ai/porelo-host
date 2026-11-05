# HO126 — A Reverted Pool VM Keeps The Snapshot's Clock

**Status:** Backlog, by the operator's word: it goes in after the release's test, on the next snapshot.

**What must be true.** A pool VM handed out after a revert has the host's time, so that `apt` in it does not refuse what
was published after its base snapshot. A VM whose clock cannot be set says so and is not handed out.

**What is known.**

- `roles/vm_pool/tasks/vm.yml` takes the base snapshot of a running VM, so with its memory, and `porelo-pool-revert` does
  `snapshot-revert base --running`. That is no boot, so nothing syncs the clock with the host at a start, and nothing
  sets it after. The same code runs on any host, rented too.
- **Measured on a passing pool leg, in seconds since the epoch, at each rental.** Before any revert: host 1793864202, VM
  1793864202. After each of four reverts: VM 1793863722, 1793863721, 1793863721, 1793863721, with the host at 1793864215,
  1793864230, 1793864244, 1793864329: the VM is back at the snapshot's moment each time, here 493 to 608 s behind, and
  `timedatectl`'s `NTPSynchronized` says `yes` all the same, from the same memory.
- The local pool leg failed twice at its real install, on the Porelo repository's `InRelease is not valid yet`, once by
  23 s and once by 7 min 17 s. Those two runs' clocks were not read; a publish after the snapshot explains them.
- The gap is as old as the snapshot, so a host that lives for days gives its renters a clock days behind, until the
  VM's time sync corrects it, how soon has not been measured, and any repository published since is refused.
- CI runs the pool off, so CI does not show it.

**The way, by the operator's word:** Porelo sets the clock itself after the revert, by the guest agent's `guest-set-time`,
with the host's time: `virsh domtime --now`, not the form without a value, which only reads the guest's own hardware clock.
Neither the guest agent nor its channel is asked for by the role today, so `porelo-vm make` needs the channel and the pool's
cloud-config the package.

**Started, not proven:** a local branch `clock` has the revert's retry, the VM left off with its reason and not reverted
over and over, the agent's channel and package, with unit tests over a stub. It has run on no VM. To check there:
whether `guest-set-time` needs the guest's `hwclock`, and a repository published after the snapshot read by `apt` in a
rental.

**Acceptance.** On the pool leg: a repository published after the snapshot, then `apt` in a rented VM after a revert,
which fails with the setting of the clock removed. A pool made before this: what `up` and the revert say.
