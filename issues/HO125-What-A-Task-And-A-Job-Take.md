# HO125 — What A Task And A Job Take

**Status:** Idea.

**What must be true.** `porelo.host.measure` also reads a task, an agent's fixed start, and a Maven build in a job at 1, 2 and 4
parallel jobs, cold and with the cache, so a size can rest on what work takes and not on an idle host.

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
  tested not to reach any other `up`.

## What it opens

- **[HO119](README.md#ho119)'s sizes:** each "not measured" there, the rule for parallel jobs, and what a person gives up below a size.
- **`disk_free_gib`** in the check's limits, unset until work's disk is read.

