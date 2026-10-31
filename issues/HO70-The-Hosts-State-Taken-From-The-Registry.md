# HO70 — The Host's State Taken From The Registry

**Status:** Review.
**Size:** M - the registry's intake in root's sync and admit and register checked against it, with unit tests and a VM
run; measured M median 63 min, from three M builds (47, 63, 75).
**Blocked by:** Porelo's registry verify.

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** The host takes which project admins and projects it has from the signed registry state the host
admin's Porelo brings it, never from the central forge itself.

- The host admin's Porelo uploads a bundle of the registry repository through the tunnel into their account's setup
  directory, as a project's access bundle goes today. Root's sync verifies it in its isolated unit with Porelo's
  registry verify and applies the answer; the host parses no signature itself.
- The anchor: the host anchors on its pinned host admin alone, with no forge and no `owners.yml`: at setup it pins the
  key that signed its host card, and Porelo's verify accepts `hosts/<host>/…` only when signed by that key or its named
  successor. A handover advances the pin, like at setup.
- A brought state must descend from the last one the host applied, as a project's second bring does today; an older or
  forked bundle is refused, so no lock, revocation or handover is rolled back.
- `access.yml` names each project admin by login and key fingerprint. A project admin registers a project only where it
  names them for it. A project dropped there is refused at its next sync and named in the sync's answer for the host
  admin; the host never removes it on its own.
- A sync that meets a bad entry names it and keeps applying the rest, so a refused login never holds up a lock or a
  revocation in the same run.

## Tests

- a bundle signed by another key, or not descending from the applied one, is refused whole; a dropped project is named
  and kept; a re-admitted purged login is refused alone while a lock in the same bundle applies.

## Acceptance

- [ ] a bundle signed by another key, or not descending from the applied one, is refused whole;
- [ ] a project the registry no longer names is named in the intake's answer and kept, and its next sync and a new
  `porelo-host-project add` for it are refused;
- [ ] a re-admitted purged login is refused alone while a lock in the same bundle applies.

## Plan

- The intake: the host admin's Porelo uploads `registry.bundle` into `~/.local/share/porelo-host/setup/` (beside the
  projects' directories; a project name holds no dot). `porelo-host-person registry`, for root or `sudo -n` from the
  pinned host admin (a new line in `porelo-host-person.sudoers`), copies it like `copy_admin_bundles` into a fresh
  directory under `/run/porelo-host/sync/` and runs `porelo registry verify --repository <credential> --host <host>
  --pinned <fingerprint> --json`, with `--since <applied commit>` once one is applied, in the same throwaway
  `DynamicUser`/`PrivateNetwork` unit as `verify_bundles` (unit `porelo-host-registry`; the staging and the
  `systemd-run` call become shared helpers). `<host>` is `forge.conf`'s `host=`. Exit 65 from Porelo refuses the whole
  bundle, a foreign signer and an older or forked state alike; the host parses no signature.
- Where state lives: root's `/etc/porelo-host/registry/` (0700). `pin.conf` (0600) holds `admin=<login>` and
  `key=<ssh-ed25519 key>`; the fingerprint is taken from the key. `applied.json` (0600) holds the applied answer:
  `commit`, `host_card`, `projects`, `persons`, and `revoked`, every login the host ever applied as revoked.
- The pin: `porelo-host-person registry pin <login> <key>`, root's alone (the sudoers rule grants persons only the bare
  `registry`), once, at setup, with the key that signed the host card; a second pin is refused. A verified handover
  advances it: when the answer's `host_card.signed_by` is another fingerprint, the pin moves to the person whose key
  has it; none such refuses the whole bundle.
- Bad entries: each project (`name`, `admin`, `access_repository`) and person (`login`, `ssh`, `expires`, `revoked`) is
  checked alone; a bad or duplicate one is named in the answer's `refused` and left out, the rest applies. A login in
  `revoked` that comes back unrevoked is refused alone and stays revoked, so a purge is never undone by an older card.
- A dropped project: every `/etc/porelo-host/projects/<p>.conf` the applied registry does not name for its recorded
  admin is named in the answer's `dropped` and kept. `sync <project>` refuses (65) a project the applied registry does
  not name for its recorded admin, before copying any bundle; `porelo-host-project add <project> <admin>` refuses the
  same before the forge.
- Answer: `{"commit", "pinned", "projects", "dropped", "revoked", "refused", "unchanged"}`, no key.
- Not here: `authorized_keys`, the KRL and ending sessions ([HO68](README.md#ho68), [HO75](README.md#ho75)); they read
  `persons` and `revoked` from `applied.json`. Wiring the pin into the setup's role run comes with
  [HO68](README.md#ho68)'s seeding of the host admin's key.
- Red first: unit tests with a fake `porelo` behind `systemd-run`, in `test_porelo_host_person.py` (refused whole on 65
  with nothing recorded; `--since` passed; dropped project named and kept; re-admitted revoked login refused alone
  while a new revocation applies; handover advances the pin; the pin set once, root alone; sync refuses an unnamed
  project) and `test_porelo_host_project.py` (add refused for a project or admin the registry does not name).

## To be checked

- Porelo's registry verify names no `--since`; descent is checked by Porelo as `project verify --since` does. Core adds
  it, or the host checks ancestry another way.
- Porelo's registry verify does not say who signed the host card; the handover reads `host_card.signed_by` (a `SHA256:`
  fingerprint).
- What `admins` holds; the host records it as answered and does not read it.
