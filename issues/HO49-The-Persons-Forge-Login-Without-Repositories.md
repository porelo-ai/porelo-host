# HO49 — The Person's Forge Login Without Repositories

**Status:** Implementing (sprint 6h; filed and estimated on the operator's word, 2026-10-28).
**Size:** S - the forge role's person tasks moved ahead of the migration and out of its condition, the Owners team
kept behind it, one Molecule check, the docs.

**What must be true.** Wherever the host runs its own forge, the person signs in to it with their lasting password,
whether or not repositories are migrated into it.

## Why

The operator, 2026-10-28: migrating repositories is the organization's matter, and the person's login must not hang on
it. Today `roles/forge/tasks/main.yml` makes the login and installs `porelo-host-forge-password` only
`when: forge_repositories | length > 0`, so a forge with no repositories has nobody to sign in, and
[HO35](README.md#ho35)'s sign-in step cannot be walked there.

## Plan

- `roles/forge/tasks/person.yml` keeps the person's account and the password script and runs with every forge, after
  the admin and before the migration.
- The Owners team moves to `roles/forge/tasks/owner.yml`, still only with repositories, since the organization is made
  by the migration.
- The test that goes red first: after the `up` the scenario has refused for the central token, before any repository is
  migrated, `operator` is a user of the forge and the script is installed.

## Acceptance

- Molecule: that check, red against the old order, green with the new; the sign-in with the lasting password as before.
