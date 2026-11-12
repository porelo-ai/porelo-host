# HO171 — The Fallback Ubuntu Mirror Removed

```json
{
  "$schema": "issue-1.json",
  "id": "HO171",
  "title": "The Fallback Ubuntu Mirror Removed",
  "state": "Review",
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

## As built

- `build/apt-fallback.sh` and `build/apt-fallback.cloud-config` are gone, with their three uses: the Build's molecule
  job installs from Canonical alone, and `build/molecule.sh` and `build/rehearse-move.sh` seed their VMs without a
  part of their own. grep finds no `apt-fallback` outside the issues.
- Measured 2026-11-12, about 19:20Z: Canonical's archive, its security suite and cloud-images.ubuntu.com answer 200
  from this machine. A bare rehearsal VM made without the part names `archive.ubuntu.com` and `security.ubuntu.com`
  in its `ubuntu.sources`, and `apt-get update` there exits 0 on them; the VM is deleted again.
- The Build run on Canonical's archive comes with the push.
