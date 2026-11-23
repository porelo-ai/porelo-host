---
name: host-build
description: porelo-host's programs and build: the files that are not Java, the four programs that may reach a host, units and sudo rules, the pre-receive hook, the workflow steps before Push ready. Use before changing any of these or saying Push ready.
---

# host-build

## Work in this repository

- **Files that cannot be Java, and why:** `mvnw`, the Maven wrapper that fetches the shared build tools by
  `build/pom.xml`, which builds nothing; `build/tools.sh`, `build/sanity.sh`, `build/check-tarball.sh` and
  `build/molecule.sh`, shell, since they run the container, read its tarball and drive libvirt where the collection is
  checked;
  `build/move-check.sh`, shell, since it only reads Porelo's and the forge's answers during an agent's move, on a
  development machine and a host that need no Java for it;
  `build/rehearse-move.sh`, shell like `build/molecule.sh`, since it drives libvirt and ssh to rehearse a move on a VM;
  `build/stage-packages.sh`, shell, since it stages and checks local Debian inputs before the test container runs;
  `build/porelo-vm`, shell, since it drives virsh on a development machine for Molecule and the rehearsal and is
  never installed on a host; `roles/vm_pool/files/porelo-pool-give-back`, shell, since it runs inside a pool VM;
  `roles/forge/templates/porelo-forge-pre-receive.j2`, shell, since it is the pre-receive hook inside Forgejo's container,
  a template only for its wait on the push judge;
  `roles/check/files/porelo-host-check`, Python's standard library, since it runs on a machine before anything is installed;
  `roles/measure/files/porelo-host-measure`, Python's standard library, since it measures a host without Java;
  `build/measure-tables.py`, Python, since it reads the result files without running the measured machine;
  `build/check-snapshot.py`, Python, since it reads the snapshot's `latest.json` where the Build runs, before Java;
  `doc/images/local-forge-svg.py`, Python like the collection's plugins, since it draws the document's picture; and the
  collection itself is YAML.
- **Only four collection programs may reach a host:** the forge's pre-receive hook, `porelo-host-check`,
  `porelo-host-measure` and a pool VM's `porelo-pool-give-back`. Host administration belongs to the pinned
  `porelo-host` package; systemd units and sudo rules remain collection configuration.
- **Host program units set no extra environment variables or environment files.** Its sudo rules name only task
  start, end and show, the two forge token verbs and `org follow-now`, with `env_reset`, `!setenv` and `!env_keep`
  command defaults.
- **The collection installs the pre-receive hook at `/usr/local/libexec/porelo/pre-receive`**, also mounted at that
  path in Forgejo; the host program links repository hooks there. Follow, forge gates and pool work use the package.
  The package has no socket push judge, so forge setup refuses before service changes and the judge unit fails closed.
  Runtime restoration belongs to `org follow`; it purges removed people after seven days, with no manual purge verb.
- **Before Push ready, every step of `.github/workflows/build.yml` runs by its own command:** `build/sanity.sh`
  runs no yamllint, so its green says nothing of the YAML step's line length.
