# HO134 — A Project's Why Gathers Its Repositories' Reasons

**Status:** Backlog.
**Kind:** Bug.
**Size:** XS - one function of the root helper and its unit tests.

**What must be true.** A project's `why` in `org status` and `org refresh` is one short line. Like reasons of its
repositories are gathered with the repositories' names, and the detail of each stays in that project's
`repositories[]`. A project that is carried with some of its repositories taken and the rest only without a central
address has no `why` at all.

## Why

`project_why` in `roles/porelo/files/porelo-host-person` joins one `<repository>: <reason>` per waiting repository.
On a host carrying porelo, whose project file gives 15 of 17 repositories no central address, the same sentence
stood 15 times in the project's `why`, and the window showed it as it is (operator, 2026-11-06). The interface shortens
its row on its side.

## Plan

- **Gathered:** the repositories' reasons are grouped by reason, each group said once as `<n> repositories <reason>:
  <names>` (one repository: `<name>: <reason>`), sorted by name, after the project's own reasons as today.
- **Null where nothing stands in the way:** a repository without a central address is a choice of the project file,
  not a fault. It is said in `repositories[]` alone and gives the project no `why`. A project whose only reasons are
  those has `why` null.
- **Red first:** a unit test of `org status` with 15 repositories without a central address and two taken, expecting
  `why` null; and one with two repositories waiting for a token and one refused, expecting two gathered groups.

## Acceptance

- The two unit tests, seen red on today's `project_why` and green after.
- `repositories[]` unchanged: each repository with its state and reason as today.
