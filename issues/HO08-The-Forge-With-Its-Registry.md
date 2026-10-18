# HO08 — The Forge With Its Registry

**Status:** Estimated.
**Size:** M - one role around a container and its runner, with credentials made and kept on the host; no state the
store must keep, since its repositories come back from the central forge.

**What must be true.** Where the project asks for one, a local Forgejo with its Actions runner and its package
registry runs on the host after `up`, as the account's own services; a project that asks for none comes up without
it, and `down` stops it without losing anything the next `up` could not make again.

## Plan

- **The playbook is the "outside"** where [PJ22](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj22) has the local Forgejo set up: outside `project.yml`
  and the project's tasks, before any task runs.
- **One role, `forge`**, run only when the inventory Porelo writes names a forge: `service.yml` (Forgejo in rootless
  podman as a quadlet user unit, its image pinned by version and digest, on the VPN's address only
  ([HO05](README.md#ho05))), `runner.yml` (the Actions runner the same way, registered once), `mirrors.yml` (a mirror
  of each repository the project names, from the central forge).
- **Credentials made on the host, kept on the host**: the admin account and the runner's registration token are made
  by Forgejo's own command line inside its container, and the person's token for the central forge is deposited by
  [HO02](README.md#ho02) into the vault; none of them is a variable, a fact or an output.
- **Nothing kept**: the repositories come back by their mirrors, and the registry is filled again by the builds;
  `down` stops the units and keeps nothing for [HO07](README.md#ho07).
- **Red first**: `verify.yml` pushes a package to the registry and reads it back through the VPN's address, and
  asserts the public address refuses; it fails with the forge bound to all addresses.

## Acceptance

- On the test VM `build/molecule.sh` makes: a workflow of a mirrored repository runs on the runner and publishes into the
  registry; a second `up` changes nothing and registers no second runner.
- A project file without a forge leaves the host without Forgejo, its image, its units or its ports.

## To be checked

- How the mirrors are kept current: pulled on a schedule, or pushed by the central forge; porelo-buildtools' push
  mirrors through the forge's API are about the other direction.
