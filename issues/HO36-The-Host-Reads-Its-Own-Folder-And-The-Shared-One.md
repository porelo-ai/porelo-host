# HO36 — The Host Reads Its Own Folder And The Shared One

**Status:** Analyzed.
**Size:** M - a few lines in one role, but a contract porelo-frontend writes (the host's name and the drive's
layout), its docs and a Molecule check.

**What must be true.** Several hosts share one tresor: each reads its own files from `hosts/<name>/` and what every host
needs from `shared/`, and the person who keeps one tresor per host uses the same layout in it. The drive holds no
secret, so a host that syncs the whole tresor sees the other hosts' files but none of their keys. This is the host's
part of porelo-project [PJ50](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj50).

## Plan

Read in the code, nothing measured.

- **The host's name**, a new collection variable `porelo_host_name` that porelo-frontend's inventory writes beside
  `porelo_host_tresor`, checked against `^[a-z][a-z0-9-]{0,30}$` by the first task of `roles/porelo/tasks/main.yml`, in
  `up`'s first play, before any path is built from it. Each role that needs it maps it to a prefixed variable of its own
  in `defaults/main.yml` (`porelo_name: "{{ porelo_host_name }}"`), declared in its `meta/argument_specs.yml`, as
  `drive_tresor` maps `porelo_host_tresor`. It is the project's name, since a project has one host, not the
  provider's, so it survives renting the host again.
- **The layout on the drive**, every file without a secret ([HO37](README.md#ho37) takes the secrets off it):
  - `hosts/<name>/machine.yml`: `porelo_machine_file` in `roles/porelo/defaults/main.yml` becomes
    `/srv/porelo-host/drive/hosts/{{ porelo_name }}/machine.yml`, from `porelo-host/machine.yml`; its entry in
    `roles/porelo/meta/argument_specs.yml` loses its fixed default and names the template in its description, as
    `drive_tresor`'s does;
  - `shared/`: what every host reads. Nothing on the host reads it yet; the lasting forge CA and password of
    [HO35](README.md#ho35) are secrets and live in the `shared` group of `secrets.kdbx`, not here;
  - `wireguard.key` and `forge-central.token` leave the drive for `secrets.kdbx`, with [HO37](README.md#ho37).
- **The old layout is refused, not read:** where `hosts/<name>/machine.yml` is missing and `porelo-host/machine.yml` is
  there, `up` stops naming both paths and the move, so a person's old tresor is never read half.
- **One mechanism for the drive, unchanged:** Tresorit syncs the whole tresor, as `roles/drive/tasks/sync.yml` does
  today; with no secret on the drive, no subfolder sync is needed.
- **Split out, not in this issue:** the person's own account on the host and their private drives mounted there, which
  [PJ50](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj50) names too. It needs a second login
  at the stop, a second mount and `down`'s wait over several drives, and [HO35](README.md#ho35) does not wait on it; it
  comes as an issue of its own once the analysis is read.
- **Touches:** `roles/porelo/tasks/main.yml` (the name's check), `roles/porelo/defaults/main.yml`,
  `roles/porelo/meta/argument_specs.yml`, `roles/porelo/README.md`, `roles/porelo/tasks/project.yml` (the refusal),
  `doc/index.md`, the Molecule scenario's inventory, and porelo-frontend's inventory and wizard, which write the name
  and the layout.
- **Red first, in Molecule:** with only `porelo-host/machine.yml` on the drive, `up` stops naming the move; with a name
  outside the pattern, `up` stops before any path is built.

## Acceptance

- Two inventories with different names and one drive folder holding both `hosts/<name>/` each read their own
  `machine.yml`.
- An old tresor with only `porelo-host/` is refused with both paths named.

## To be checked

- With porelo-frontend, how the wizard moves an existing tresor's `porelo-host/` files into the new layout.
