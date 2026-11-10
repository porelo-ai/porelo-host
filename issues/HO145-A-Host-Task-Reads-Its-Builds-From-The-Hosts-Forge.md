# HO145 — A Host Task Reads Its Builds From The Host's Forge

```json
{
  "$schema": "issue-1.json",
  "id": "HO145",
  "title": "A Host Task Reads Its Builds From The Host's Forge",
  "state": "Review",
  "size": "S",
  "priority": "Medium",
  "rank": 9,
  "blockedBy": [],
  "covers": "A host task reads its Builds from the host's forge: the follow names `builds` in each project's file beside `fetch_from`."
}
```

**Why this size.** the follow writes `builds` into each project's file on the host beside `fetch_from`, with its tests and
docs.

**What must be true.** A task of a guarded project on the host reads the Builds of its pushes from the host's forge,
as the person who started it, without the project's signed `project.yml` naming anything of the host. It is a feature.

## Why

The trial move's Build line could only say `not configured`: porelo reads builds from `project.yml`'s `builds:`, and a
guarded project names none. The host's per-project file names the builds instead, so `project.yml` stays the same on
every machine and a guarded task's egress stays as it is; Porelo reads the field from that file.

## Plan

- The follow writes `builds` into `/etc/porelo-host/organization/projects/<project>.json` exactly when it writes
  `fetch_from`: `{"forge": "forgejo", "api": "http://127.0.0.1:<git_port>/api/v1", "credential": "<forge>.person",
  "logs": "failure"}`, `<forge>` being forge.conf's `name`. The credential is the vault entry
  `porelo-host-forge-token` makes. No token goes into the file.
- A forge.conf whose name does not read leaves `builds` out, says so, and fails nothing else of the follow.
- **Red first:** the follow's test of a project file on a host with a forge asserts `builds`; red today.

## Acceptance

- The unit tests, seen red on today's follow and green after.
- On the next rehearsal's host, `move-check` shows a Build of the task's push once porelo reads the field.
