# HO119 — Which Server For What

**Status:** Accepted; after the foo test.

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

## What has to be measured

| Measure | On |
| --- | --- |
| An idle host with and without Forgejo and the room: memory, disk | a fresh VM, `up` with each choice |
| One typical task, one agent: memory, disk | that host |
| A Maven build in a job: memory, CPU, disk, time | the forge's runner, with its cache |

None of this is measured yet. Local VMs give memory and disk, after the foo test; time wants a real host, which a rental needs
the operator's word for, and a time not measured there is marked so.

## The rule for parallel jobs

Today, unset: 2 jobs when two of the smallest fit, otherwise 1, each up to 4 CPUs and 8 GiB, within half the host, so the job
count stops at 2 on any machine. `forge_runner_capacity`, `forge_job_cpus` and `forge_job_memory` go beyond, within the same half.
The half itself can't be set: a person with a machine used only for builds has no way past it.

The measures answer, and the page says: how many jobs make sense at which memory; whether 2 is the right stop and half the
right share; what a person sets to go beyond, and what happens to the tasks then. A changed rule is a change to `forge`'s
capacity and its unit tests, here.

## What `up` checks

Read today: the CPU; a job budget and a pool within half the host. **No role checks disk:** a full disk shows late, as whatever
then fails. To add, with a number from the measures: free disk under the paths that grow, refused before anything is installed
and naming both sides; the same for memory below what the host's choices need. The page lists every check and its words.

## Acceptance

- The page in `doc/`, in `mkdocs.yml`'s nav, each number measured with how, or marked "not measured".
- The measures' runs named in this issue, with the run's versions.
- Too small a disk stops `up` before installing, in a unit test with the real `ansible-playbook` and in Molecule's run, or this
  issue says from the measures why no number holds.
- The interface's field for concurrent jobs and its words can take their numbers from the page.
