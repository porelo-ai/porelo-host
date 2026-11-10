# HO147 — A Host's Builds Also Read The Upstream Snapshots

```json
{
  "$schema": "issue-1.json",
  "id": "HO147",
  "title": "A Host's Builds Also Read The Upstream Snapshots",
  "state": "Review",
  "size": "XS",
  "priority": "Medium",
  "rank": 7,
  "blockedBy": [],
  "covers": "Each organization the host registers holds `MAVEN_UPSTREAM_SNAPSHOTS_URL`, Sonatype's snapshots read anonymously, so a build resolves the snapshots the host's registry lacks."
}
```

**Why this size.** one default of the forge role, its argument spec, the host check's places, two documents and a changelog
entry, with a unit test.

**What must be true.** A build on the host's forge resolves the `org.fuin.porelo` snapshots the host's own registry does
not hold, such as a parent pom or a library of another repository, from Sonatype's snapshots, anonymously, while the
organization's own snapshots still come from the forge's registry with its read token.

## Why

The host sets `MAVEN_SNAPSHOTS_URL` to its own registry, which holds only what the organization's repositories deploy,
and Forgejo's Maven registry fetches nothing from elsewhere. So every Maven step that needs another repository's
snapshot failed on the host's forge.

## Plan

- `roles/forge/defaults/main.yml`: `forge_variables` gains `MAVEN_UPSTREAM_SNAPSHOTS_URL:
  "https://central.sonatype.com/repository/maven-snapshots/"`, which the registration of an organization sets beside
  `MAVEN_SNAPSHOTS_URL`; an organization registered before keeps without it, as with every variable, and a new host
  registers its own. A repository's `forge` profile reads it as a repository with an id of its own and no
  `<server>`, after `porelo-forge`, so the forge's read token never goes there; unset, the profile reads the forge
  alone, as before.
- `roles/forge/meta/argument_specs.yml`, `roles/forge/README.md`, `doc/local-forge.md`'s table and a changelog entry.
- `roles/check/files/limits.json`: `central.sonatype.com:443` among the forge's places to reach, since the host's
  jobs fetch from there; the check names every place a role names.
- **Red first** in `tests/unit/roles/test_forge_runner_transport.py`: the defaults name the variable as an `https`
  address of Sonatype's snapshots, and the argument spec's default holds the same.

- The reading by another model also found that `forge_variables`' argument spec shows `MAVEN_SNAPSHOTS_URL` without
  `:{{ forge_http_port }}`, as before this change; the spec's default only describes the role's own, which the
  defaults file holds, so it is left as it stands.

## Acceptance

- The unit test, seen red on today's defaults.
- On the next move's host, a repository's Build resolves porelo-parent's snapshot.
