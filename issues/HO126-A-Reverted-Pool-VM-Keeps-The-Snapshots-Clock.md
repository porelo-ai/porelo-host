# HO126 — A Reverted Pool VM Keeps The Snapshot's Clock

**Status:** Review. In `v0.5.12`, before the test, by the operator's word.

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
with the host's time: `virsh domtime --now`. Plain `domtime` only reads the guest's time and `--sync` takes its hardware
clock; `guest-set-time` with no value is that same hardware-clock form.
The role asked for no guest agent before; the pool's cloud-config now installs it. `virsh domtime --now` on a real Ubuntu VM
works, `hwclock` included. Fedora is offered by the role and is untested here.

**The handling, as proposed to the coordinator.** The snapshot's memory says `ready`, and a rental reads that over ssh,
so setting the clock after starting the VM leaves a moment in which it is handed out with the old clock, and a minute if
the clock cannot be set. So `porelo-pool-revert` reverts paused, takes the VM's network link down, resumes, sets the clock
over the agent's channel, which needs no network, and brings the link up; `LocalPool` waits through an unreachable VM. A
clock that cannot be set: the VM goes off, says why, and is not reverted again until the service restarts or `up` runs.
If it cannot be stopped either, its link stays down. A VM a revert left midway, as a note beside it says, is done again at the
service's next look or the next `up`, which goes through the same code, one at a time with the service, and fails loud;
a VM paused with no such note, as libvirt pauses a rented one on a disk error, is left alone. `up` refuses a VM made
before the agent, naming `down` and `up`: a file beside the VM says its snapshot holds one, as virt-install adds the
channel to any VM. An agent that does not answer is given up on after 10 s a try, as libvirt would wait for ever.

**Acceptance.** On the pool leg: a repository published after the snapshot, then `apt` in a rented VM after a revert,
which fails with the setting of the clock removed. A pool made before this: what `up` and the revert say.

## Result

- **On the pool leg, with the setting:** the VM within 1 s of the host at all five rentals, and a repository published at that
  moment read by `apt` in the rental.
- **With the setting taken out, by hand, on a commit before the last recovery fixes, whose clock and proof are the same:** the
  leg fails at the second rental, the VM 586 s behind the host: `Release file ... is not valid yet (invalid for another 9min
  36s)`. A snapshot younger than `apt`'s 10 s, or a guest's own time sync, could hide this, so the acceptance cannot catch it on
  its own every time, and it is no CI check: CI runs the pool off.
- **A pool made before this:** `up` refuses, naming `down` and `up`; shown on the pool leg, with the file that says a snapshot
  holds an agent moved away. A real old pool has not been run.
- **Not shown on a VM:** the crash windows, the lock and the unanswered agent, which are unit tests over a stub.
