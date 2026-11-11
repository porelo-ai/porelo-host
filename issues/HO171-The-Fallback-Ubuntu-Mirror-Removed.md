# HO171 — The Fallback Ubuntu Mirror Removed

```json
{
  "$schema": "issue-1.json",
  "id": "HO171",
  "title": "The Fallback Ubuntu Mirror Removed",
  "state": "Accepted",
  "size": "XS",
  "priority": "High",
  "rank": 1,
  "blockedBy": [],
  "covers": "Once Canonical's Ubuntu archive is back, build/apt-fallback.sh, build/apt-fallback.cloud-config and their three uses go, and apt reads Canonical's archive again on the runner and in every VM."
}
```

**Why.** Canonical's archive, its DNS and cloud-images.ubuntu.com have been down since 2026-11-11 11:06Z. By the
operator's order of 16:31Z, every apt step uses a fallback mirror meanwhile. In porelo-host this is temporary:
- `build/apt-fallback.sh` points a runner's `ubuntu.sources` at `http://ftp.fau.de/ubuntu/`. The Build's molecule job
  runs it only after its pinned install has failed against Canonical, then installs again.
- `build/apt-fallback.cloud-config` does the same in every VM that `build/molecule.sh` and `build/rehearse-move.sh`
  make, through the seed. While it is in, those VMs read fau.de, not Canonical.

apt checks every Release file against Ubuntu's keyring all the same.

The Build also keeps the VM's pinned cloud image in the Actions cache, by its digest, and `build/molecule.sh` reads
Ubuntu's SHA256SUMS only when it has to download the image. Both stay: they leave a warm run green when
cloud-images.ubuntu.com is down again.

**What must be true.** Canonical's status page shows the incident closed, and a runner and a VM fetch from Canonical
again. Then the two files and their three uses (build.yml's molecule job, molecule.sh's seed and rehearse-move.sh's
seed) are removed, and grep finds no `apt-fallback` left.

## Plan

Remove the files and the three uses. Prove it with a Build run green on Canonical's archive and a bare rehearsal VM
whose `ubuntu.sources` names Canonical.
