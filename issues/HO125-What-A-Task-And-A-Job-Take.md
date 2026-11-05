# HO125 — What A Task And A Job Take

**Status:** Backlog, by the operator's word. Nobody starts it yet: it follows the test, and its rented run needs their word,
with its price and duration brought to them first.

**What must be true.** `porelo.host.measure` also reads a task, an agent's fixed start, and a Maven build in a job at 1, 2 and 4
parallel jobs, cold and with the cache, so a size can rest on what work takes and not on an idle host.

## The question it answers, the operator's

**How many developers with their tasks fit sensibly on a host of 64 GB and of 128 GB, with and without Forgejo?** A developer
holds about 5 tasks. From the per-task and per-build peaks of these runs, the number of tasks is raised until something
suffers, and the answer names what suffers first: memory, CPU, disk or the half for jobs. It is the central half of one table
of sizes; a developer's desktop is the other half, measured in the desktop's own issue on the same load: `porelo-buildtools` at
the same pinned tag and the same fixed agent start, so that the two compare.

**The default for parallel jobs is in question too.** Unset, `up` gives 2 jobs within half the host, and that depends on what
runs there. This run goes past the half on purpose and says what default the numbers support.

## The two machines, named by the operator, read on 2026-11-05

| Machine | Type | CPUs | Memory | Disk | KVM | Per hour |
| --- | --- | --- | --- | --- | --- | --- |
| 64 GB, Hetzner Cloud | `ccx43` | 16 dedicated vCPUs | 64 GB | 360 GB | not offered as far as read, not read on one | 0.4423 EUR net, `fsn1` or `hel1` |
| 128 GB, bare metal, Scaleway Elastic Metal | `EM-I220E-NVMe` | AMD EPYC 8124P, 16 cores, 32 threads | 128 GiB DDR5 | 2 x 960 GB NVMe | yes, as bare metal; the run's own reading confirms | 0.63 EUR, hourly offer, `fr-par-1` as `porelo_host` rents it |

The prices come from Hetzner's API and Scaleway's public catalog. Scaleway's monthly offer has a setup fee of 229.99 EUR; the
hourly one lists none. Hetzner's documents say nothing of nested KVM, and third-party notes say a cloud server has none, so
a VM pool or a job that makes a VM is measured on the bare metal only, and the run's first reading says what `ccx43` has.

**Read across, or rent both?** Rent both, as named, the smaller first. What a task and a build take in memory and disk adds up
and can be read across, from a smaller host too; that is a hypothesis this run tests. What suffers under load cannot: CPU
contention and the half depend on the thread count and on dedicated against bare metal, and those differ here by twice the
threads. So `ccx43` gives the per-task figures and a predicted number for 128 GB, and the bare metal checks that number. If it
holds, later sizes can be read across. Duration and price are estimated when the run is built; the operator's word follows them.

## Why

[HO120](README.md#ho120)'s run reads the machine before `up` and each idle shape, and writes "not measured" for these three. A
task and an agent's start need a person and a vault on the host, and a job needs a project on the forge, none of which the
idle run makes. **Until this is done, a size that has to hold work does not rest on a measured number.**

## Already settled, in HO120's analysis

- **The Maven project:** `porelo-buildtools` at a pinned tag, so the number can be run again. It reaches Maven Central, whose speed
  is in the cold number.
- **An agent:** idle and a fixed start only. Real work stays "not measured", as it needs a token, costs money, and a model's answer varies.
- **More than the half:** 4 jobs on a small machine are refused by `forge`'s capacity check, and showing what happens past it is the
  point. It takes a variable the measuring run alone sets, and it has to reach `up` there. The first one set a variable in a play
  that starts `up` as a separate process, so it never arrived, and it was taken out unused. Pass it on the run's own command line,
  tested not to reach any other `up`. [HO127](README.md#ho127)'s setting replaces that variable, so it comes first.

## What it opens

- **[HO119](README.md#ho119)'s sizes:** each "not measured" there, the rule for parallel jobs, and what a person gives up below a size.
- **`disk_free_gib`** in the check's limits, unset until work's disk is read.

