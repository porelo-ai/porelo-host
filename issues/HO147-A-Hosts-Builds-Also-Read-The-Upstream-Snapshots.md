# HO147 — A Host's Builds Also Read The Upstream Snapshots

**Status:** Implementing.
**Size:** XS - one default of the forge role, its argument spec, two documents and a changelog entry, with a unit test.

**What must be true.** A build on the host's forge resolves the `org.fuin.porelo` snapshots the host's own registry does
not hold, such as a parent pom or a library of another repository, from Sonatype's snapshots, anonymously, while the
organization's own snapshots still come from the forge's registry with its read token.

## Why

The host sets `MAVEN_SNAPSHOTS_URL` to its own registry, which holds only what the organization's repositories deploy,
and Forgejo's Maven registry fetches nothing from elsewhere. So every Maven step that needs another repository's
snapshot failed on the host's forge.

## Plan

- `roles/forge/defaults/main.yml`: `forge_variables` gains `MAVEN_UPSTREAM_SNAPSHOTS_URL:
  "https://central.sonatype.com/repository/maven-snapshots/"`, which `up` sets on each new organization beside
  `MAVEN_SNAPSHOTS_URL`. A repository's `forge` profile reads it as a repository with an id of its own and no
  `<server>`, after `porelo-forge`, so the forge's read token never goes there; unset, the profile reads the forge
  alone, as before.
- `roles/forge/meta/argument_specs.yml`, `roles/forge/README.md`, `doc/local-forge.md`'s table and a changelog entry.
- **Red first** in `tests/unit/roles/test_forge_runner_transport.py`: the defaults name the variable as an `https`
  address of Sonatype's snapshots, and the argument spec's default holds the same.

## Acceptance

- The unit test, seen red on today's defaults.
- On the next move's host, a repository's Build resolves porelo-parent's snapshot.
