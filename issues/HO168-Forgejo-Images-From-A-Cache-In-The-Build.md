# HO168 — Forgejo Images From A Cache In The Build

```json
{
  "$schema": "issue-1.json",
  "id": "HO168",
  "title": "Forgejo Images From A Cache In The Build",
  "state": "Estimated",
  "size": "M",
  "priority": "Medium",
  "rank": 5,
  "blockedBy": [],
  "covers": "The Molecule job takes the forge role's three pinned images from a cache kept by their digests, so an outage of codeberg.org, code.forgejo.org or docker.io leaves it green; only the newest digests stay cached."
}
```

**Why this size.** It has four parts:
- a workflow step that fills and restores the cache;
- a way to hand the archives into the Molecule VM;
- a role option to load an archive before the pull;
- a proof with the registries unreachable.

Each part is small. Their seams are new: an archive's digest must survive the load, so that `podman image exists
<name>@sha256:…` answers yes. That has to be seen to work, not assumed.

**What must be true.** Part of ST317. porelo-host's `molecule` job (both `kvm: on` and `off`) passes when codeberg.org,
code.forgejo.org and docker.io do not answer, as long as the pinned digests are in the cache. On 2026-11-11 Codeberg's
registry answered 504 in CI and 503 in a VM rehearsal (09:30Z) for Forgejo's image, and each run went red at
`porelo.host.forge : service | Pull Forgejo's image by its digest`.

## What is downloaded today

The forge role pulls three images, each pinned by version and digest in `roles/forge/vars/main.yml`:

| Image | Registry | Used by |
|---|---|---|
| `__forge_image`, Forgejo 17.0.0-rootless | codeberg.org | the forge |
| `__forge_runner_image`, Forgejo's runner 13.2.0 | code.forgejo.org | the forge's runner |
| `__forge_runner_proxy_image`, alpine/socat 1.8.1.3 | docker.io | the runner's socket proxy |

ST317 named only the first. The other two fail the same way when their registry fails, so this issue takes all three.
The same mechanism costs nothing more per image.

Two other outside downloads are not part of this issue:
- `build/tools-image` (ghcr.io, the Ansible tools) runs on the runner's own podman.
- The pinned apt packages of the `molecule` job come from Ubuntu's archive.

Both are for porelo-host's ST317 list, as their own lines.

## Plan

**A ready-made action or our own steps.** Our own steps. The usual container cache actions save and load the runner's
**docker** image store, keyed by the image name. That does not fit here:
- The images are needed inside the Molecule VM, in the forge account's **rootless podman**, not on the runner.
- Our own cut is an archive file per digest. A file can go into the VM the way `PORELO_HOST_PACKAGES` already does, and
  the role can load it.
- No third-party action is needed. The only action is `actions/cache`, pinned by commit like the others, which the
  workflow already trusts.

The steps:
1. **Fill and restore.** A step reads the three references from `roles/forge/vars/main.yml`.
   - `actions/cache` restores `$RUNNER_TEMP/images`, keyed by a hash of the three digests.
   - On a miss, `skopeo copy --preserve-digests docker://<ref> oci-archive:$RUNNER_TEMP/images/<digest>.tar` fetches
     each image once, and `actions/cache` saves them at the job's end.
   - skopeo is on the runner image; its version is checked like the apt pins.
2. **Into the VM.** `build/molecule.sh` passes `PORELO_HOST_IMAGES=<dir>` on to the scenario, beside the packages.
   `converge.yml` copies the archives into the VM.
3. **The role loads before it pulls.** A new role option `forge_image_archives` names a directory on the host. For each
   pinned image whose archive is there, the role loads it into the account's podman before the existing "Ask podman
   whether … is there" task. The role refuses an archive whose digest is not the pinned one.
   - Loading must leave `podman image exists <name>@sha256:<digest>` true. An oci-archive loaded by `podman load` may
     keep no repository digest. If it does not, the role copies with `skopeo copy --preserve-digests
     oci-archive:… containers-storage:<name>@sha256:…` instead. Which one works is seen first.
   - The role pulls only an image whose archive is missing, so a host without the option behaves as today.
   - The option is also what an air-gapped host would use.
4. **Down and up again.** `down` removes the forge account's storage, and the scenario's side effect runs `up` again.
   The role therefore loads at every `up`, not once per scenario.
5. **Tests.**
   - A unit test checks the role's order (load, exists, pull) and its refusal of a wrong digest.
   - The proof is a CI run with the three registries blocked in the VM, by `/etc/hosts` entries to 0.0.0.0 set for that
     run only. It is first seen red without the cache (the pull fails), then green with it.
6. **Docs.** The role's README gets `forge_image_archives`, and `doc/testing.md` gets the cache.

## Only the newest state is kept

- The cache key is the hash of the three digests. A new pin makes a new key, and the old key is never restored again.
- GitHub removes a cache entry that was not used for 7 days, and the repository's total is capped. So an old digest's
  entry ages out by itself.
- To be checked: whether the repository's Actions settings in this account let the retention be set shorter. If they
  do not, a step after a successful save deletes every other `forge-images-` key with `gh cache delete`. That needs
  `actions: write` for this one job; I prefer the 7-day expiry unless the operator wants the step.

## Acceptance

- `molecule` (on and off) green with codeberg.org, code.forgejo.org and docker.io blocked in the VM, the cache warm.
- The same run without the cache red at the pull, which shows the block works.
- A second push with unchanged pins restores the cache and fetches nothing.
- A changed pin fetches once under a new key, and the old key ages out.
