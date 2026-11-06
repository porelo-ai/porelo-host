# HO135 — The Host's Copy Follows A File Signed Anew

**Status:** Accepted (operator, 2026-11-06).
**Kind:** Bug.
**Size:** S - the advance script's target and the follow's record of it, with unit tests and a Molecule step.

**What must be true.** The follow brings the project's own `main` on the host's forge up to the commit Porelo judges
the project file by: the newest commit on the first-parent line that changed `project.yml` or carries the trailer
`Porelo-Signs-Anew: project.yml`. The follow records as advanced only the commit the forge's `main` reached.

## Why

On the rehearsal's host (operator, 2026-11-06), porelo-project's GitHub `main` was `cf7e948`, an empty commit that signs
the file anew, over `656fa56`, the unsigned change. The follow verified `cf7e948` and took the repositories it named.
But `project-advance` in `roles/forge/files/porelo-host-project` targets `git log -1 -- project.yml`, the newest commit
that changed the file, wherever the repository has workflows. So it moved the forge's `main` to `656fa56`, and Porelo
refused every task: "the commit has no readable SSH signature". The follow recorded `cf7e948` as advanced, so the
project's `why` said nothing.

## Plan

- **The target:** in `ADVANCE_SCRIPT`, the newer of the last first-parent commit that changed `project.yml` and the
  last one whose trailers carry `Porelo-Signs-Anew: project.yml`. It must still hold the same `project.yml` as the
  verified commit, and `main` moves only forward. A sign-anew commit changes no file, so the diff check from the local
  `main` still passes.
- **The record:** the script answers the commit `main` stands on, and the follow keeps that as `advanced`. Where it is
  not the verified commit's judged one, the project's `why` says a task reads an older project file.
- **Red first:** a unit test of the script on a repository with workflows whose tip signs anew, expecting `main` at
  the tip; today it stops one below.
- **Molecule:** the follow act signs the stand-in project's file anew with an empty commit and expects the forge's
  `main` at it.

## Acceptance

- The unit test, seen red on today's script and green after; the Molecule scenario green with the sign-anew step.
- A task on a project whose newest signature is a sign-anew commit starts on a host.

## To be checked

- That Porelo's rule is read the same: `ProjectFile.judged` and `TreeRepository.signingAnew` in porelo, which take the
  first-parent line, as Agent Core named them.
