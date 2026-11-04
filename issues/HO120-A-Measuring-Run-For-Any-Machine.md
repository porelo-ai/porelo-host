# HO120 — A Measuring Run For Any Machine

**Status:** Backlog.

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
| One task, then one agent | memory peak, disk growth, start time |
| A Maven build in a job, at 1, 2 and 4 parallel jobs, cold and with the cache | memory peak, disk growth, time, CPU |

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

## Settled for building

- **The Maven project:** `porelo-buildtools` at a pinned tag, so the number can be run again; it reaches Maven Central, whose
  speed is in the cold number.
- **More than the half:** 4 jobs on a small machine are refused by `forge`'s capacity check, and showing what happens past it
  is the point. A role variable the measuring playbook alone sets takes the run past the check, tested not to reach `up`.
- **An agent:** idle and a fixed start only; real work is "not measured", as it needs a token, costs money, and a model's answer varies.

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
