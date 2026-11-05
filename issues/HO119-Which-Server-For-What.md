# HO119 — Which Server For What

**Status:** Review.

**What must be true.** A person reads one page and knows which server to take for what they will run: system, CPUs, memory,
disk, KVM yes or no. Each number on it is measured, or marked "not measured". What `up` can tell early it refuses early.

## Why

The only numbers today are bounds in `doc/index.md` and `roles/forge/README.md`: what Forgejo, the runner and a job may take.
They say nothing of what a host needs, and no page recommends one. The `vmx` and `svm` line under "You need" in the first-run howto, moved to `porelo/doc` later, is the nearest thing, and with [HO118](README.md#ho118) it is wrong for most hosts.

## The page

- **Two shapes:** tasks only, with a central forge and no Forgejo; and with Forgejo and N parallel builds.
- **For each:** system, CPUs, memory, disk, KVM yes or no, and what a person gives up below it.
- **KVM** comes from [HO118](README.md#ho118)'s setting: a VM pool or a job that makes a VM.
- **It replaces** that line of the first-run howto.

## Where the numbers come from

From [HO120](README.md#ho120)'s measuring run, one result file per machine, and the page says which machine each number came
from. A new machine class is one more run. What no run has shown is marked "not measured". Local VMs first, after the foo test;
no rental without the operator's word.

## The rule for parallel jobs

Today, unset: 2 jobs when two of the smallest fit, otherwise 1, each up to 4 CPUs and 8 GiB, within half the host, so the job
count stops at 2 on any machine. `forge_runner_capacity`, `forge_job_cpus` and `forge_job_memory` go beyond, within the same half.
The half itself can't be set: a person with a machine used only for builds has no way past it.

The measures answer, and the page says: how many jobs make sense at which memory; whether 2 is the right stop and half the
right share; what a person sets to go beyond, and what happens to the tasks then. A changed rule is a change to `forge`'s
capacity and its unit tests, here.

## What is checked at `up`

[HO121](README.md#ho121) holds the one check before any installation, disk too. This page lists its findings in the person's words,
and its measured numbers go in that check's limits.

## Acceptance

- The page in `doc/`, in `mkdocs.yml`'s nav, each number measured with how, or marked "not measured".
- Its tables made from [HO120](README.md#ho120)'s result files, at least two machines' worth.
- [HO121](README.md#ho121)'s limit for free disk set from the measures, or this issue says why no number holds.
- The interface's field for concurrent jobs and its words can take their numbers from the page.

## Result

The page stands in `doc/machines.md`, its summary made from [HO120](README.md#ho120)'s three files. **It recommends no size,** as the page may not rest on what
is not measured, and says so at its head: each size is "not measured", with the idle figures beside it.

- **Its tables:** the summary and the machines' come from the files; "What to take" is written by hand, as every size in it is "not measured". The files are three local VMs on one
  machine, differing only in memory: at least two machines' worth in number, not in kind.
- **So what must be true is not yet true:** a person cannot yet read which server to take. [HO125](README.md#ho125) opens that, and the rented rows wait on the operator's word.
- **Free disk:** `disk_free_gib` stays unset, as idle numbers say nothing of what work fills. It waits for [HO125](README.md#ho125).
- **Parallel jobs:** the rule is stated and not judged. How many jobs make sense, and whether 2 and half are right, need [HO125](README.md#ho125).
- **The interface's field for concurrent jobs** has no measured number to take yet; it can take the rule's words and its bounds, 1 CPU and 768 MiB to 4 CPUs and 8 GiB.
- **The first-run howto's line** lives in `porelo/doc`, and is not changed from here.
