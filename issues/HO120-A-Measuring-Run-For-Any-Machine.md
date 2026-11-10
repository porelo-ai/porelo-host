# HO120 — A Measuring Run For Any Machine

```json
{
  "$schema": "issue-1.json",
  "id": "HO120",
  "title": "A Measuring Run For Any Machine",
  "state": "Review",
  "size": "L",
  "priority": "Medium",
  "rank": 28,
  "blockedBy": [],
  "covers": "One command that measures a given machine, again on any hardware, and writes one result file without secrets for the page's tables."
}
```

**Why this size.** a new playbook and role, a versioned result file without secrets, the script for the page's tables, and runs on three VMs.

**What must be true.** One command measures a given machine and writes one result file, so a new machine class is one run and
a number on [HO119](README.md#ho119)'s page names the machine it came from.

## The place, proposed

**A playbook `playbooks/measure.yml`,** `porelo.host.measure`, run on the machine with `-c local` as `up` is, since it has to
run `up` and `down` with each choice, and a role `measure` beside it. A person can run it on their own hardware from the same
tarball. Results kept here under `doc/measures/`, one file per run, and the page's tables made from them by a small script in
`build/`; a unit test fails when a table and the files differ.

## What it records

- **The machine:** CPU model and count, memory, disk size and kind, kernel, system, `vmx` or `svm`, whether `/dev/kvm` answers,
  provider and offer as given by the person. The collection's and the packages' versions.
- **In the given order, each from a settled state:**

| Step | Reads |
| --- | --- |
| The machine before `up` | memory, disk |
| Idle, each of: no Forgejo and no room; the room; Forgejo; both | memory, disk, `up`'s time |
| One task, then one agent | "not measured", [HO125](README.md#ho125) |
| A Maven build in a job | "not measured", [HO125](README.md#ho125) |

Memory from the cgroups, whose peak each unit and task already has, not from `free`. Each step is read three times and the file
holds all three; a page's number says which it shows.

## The result file

One JSON file, its schema versioned, each number with its unit and step, or `null` and why, so "not measured" comes from the
file. **It holds no secret:** it is written from an allow-list of fields and never from a command's output; a unit test feeds
in lines with a planted secret and reads the file for it. No address, host key or account of the machine.

## Lasting changes

It changes a machine, so it says what it left: it lists packages, units, accounts, and top-level directories before and after,
and the difference goes in the file. `up` and `down` are known to leave a firewall and packages, so it is for a fresh machine
that is given back, and it stops where a person holds a membership or a homeserver holds a room. A run stands alone on its
machine, as any timing measurement.

## What it reads, and not yet

**Idle only.** The machine before `up` and the four idle shapes, each read three times. A task, an agent's fixed start and the Maven
jobs say "not measured" in the file, and are [HO125](README.md#ho125), with what was settled for them. **[HO119](README.md#ho119)'s page may not
rest on them yet:** a size that has to hold work has no measured number until then.

## Hardware, in order

| Machine | KVM | Needs |
| --- | --- | --- |
| Local VMs at 4, 8 and 16 GB | yes, or off with [HO118](README.md#ho118) | nothing; shows memory and disk, not a real host's time |
| A `cx33`-like cloud server | no | [HO118](README.md#ho118), the operator's word |
| Scaleway Elastic Metal, `EM-I220E-NVME` | yes | the operator's word, its price read and posted first |

One number stands, not from this run: the interface's *Prepare the machine* took about 5 minutes on Elastic Metal with `v0.5.10`.

## Acceptance

- `up`-to-`down` run on a local VM at each size writes a file that a second run on the same VM reproduces in shape, its numbers
  side by side.
- The planted secret is in no result file; the difference it lists names what `down` left.
- A refused machine, one with a person or a room, stops before anything changes.
- The page's table is made from the files, and a changed file fails the unit test until it is made again.

## Result

**Idle, on local VMs at 4, 8 and 16 GiB, on a snapshot collection.** All three files stand under `doc/measures/`, and the page's tables come from them. All 36
`up` reached, none refused. In use, summed over the slices, is the same at each size within the readings: about 225 MiB before `up`, 230 for `none`, 290 for
`room`, 380 for `forge` and 440 for `both`. Disk at `/` goes from 2.7 to 4.5 GiB.

**A second run at 4 GiB, on the commit before the reading's fixes, has the same facts:** in use within about 15 MiB in every reading; `up`'s time moves more, past two
times in one reading, so these say nothing of a host's time. It is not kept in `doc/measures/`.

**A proof run at 4 GiB, on the commit before this text, has the same 438 facts and all `up` reached.** One reading of `both` did not settle within its 24 seconds, and the file says so
with a null; none of the kept files has one. So a null can happen on a small VM, and the settling is what it should be. That file was not kept, and its other figures were not compared.

- **Measured:** memory and disk at idle, what the run left, and `up`'s time, which says little on a VM. A planted secret stays out of the file by unit test.
- **Not shown:** a real host's time, the `cx33`-like and Elastic Metal rows, each on the operator's word and not done. What `up` takes while it runs.
- **What the difference names `down` left:** the packages, the unit files of those packages and of the firewall, the task sweep and the homeserver, `dnsmasq`'s account, and
  on the 8 GiB run `/var/lib/fwupd`. It lists no directory in `/etc` or `/opt`, and the file's own list is the whole of it.
