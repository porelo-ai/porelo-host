# HO09 — Up And Down In Their Order

**Status:** Implementing.
**Size:** M - two playbooks and the order of the roles, a stop the caller resumes from, and the output a program
reads; the roles themselves are the other issues'.

**What must be true.** `host up` and `host down`, porelo-frontend's command, each run one playbook of this collection, `up.yml`
and `down.yml`, which take the roles in their order; a run stopped halfway is started again and goes on from where it
stood, and `down` after a failed `up` takes down what came up.

## Plan

- **Decided: this order, not [PJ40](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj40)'s**: the drive comes before the VPN, since the VPN's key lies on the
  drive, and the person has one stop, for the Tresorit login and the vault; the host is reached over its public ssh
  only until the VPN is up.
- **Decided: the playbook runs on the host itself.** `host up` copies the collection's tarball and the inventory to
  the host over ssh, installs `ansible-core` from Ubuntu's packages (2.20 on 26.04), and runs `ansible-playbook -c
  local` there; `down` the same, before the host is given back. The person's computer needs only ssh and `host up`.
  So every play's target is `localhost`, and the plays take no host from the inventory.
- **`playbooks/up.yml`, two plays**:
  1. the role `porelo.host.base`, `porelo`'s install, account and setup ([HO02](README.md#ho02)), `drive`'s
     install and daemon ([HO06](README.md#ho06)); then it ends, naming what the person runs over `ssh -t`: the
     Tresorit login and `porelo vault init|unlock`.
  2. It checks first that the drive is synced and the vault open, and stops naming the step if not; then `vpn`
     ([HO05](README.md#ho05)), the keys ([HO02](README.md#ho02)), `store`'s restore ([HO07](README.md#ho07)), `forge`
     ([HO08](README.md#ho08)), the homeserver's packages ([HO11](README.md#ho11)), `vm_pool` ([HO12](README.md#ho12)),
     follow and the tasks, and the store's timer last.
- **Resuming is idempotence**: a second `up` runs both plays from the top, and every role changes only what differs,
  so it goes on where the last run stopped; no marker file of the playbook's own.
- **`playbooks/down.yml`**, the other way round: the store's last copy, which must succeed before anything stops; the
  tasks and services stopped; `porelo vault clear --yes`; the VPN; the drive synced and unmounted last. Every step
  takes down only what is there, so `down` after a failed `up` works.
- **The room's order**: `vault clear` on an account with its own homeserver also runs the transport's `clear`, which
  removes the homeserver's database volume, its port, its registration token and its poll positions; so the room's
  copy comes before it at `down`, and at `up` the room is restored before the first `porelo task start`, which would
  otherwise make a fresh homeserver.
- **What a program reads**, as porelo-frontend's issue on putting a project on a server asks: a callback plugin of
  this collection writes one JSON line per step - started, done or refused, its name, and on a refusal the command
  that fixes it - into a file the caller names, beside Ansible's text for a person; the stop for the person is a
  refusal of its own kind, naming the host and the account. Ansible's exit codes stay as they are, and `host up` turns
  the stop into an exit code of its own, so the interface asks the person instead of showing a failure.
- **Red first**: `up` with the vault left shut must end in the stop, with its line in the file; the second `up`
  after the vault is opened must report the first play's roles `changed=0`.

## Acceptance

- On the test VM `build/molecule.sh` makes: `up`, the stop, the person's step done by the test, `up` again, all green; `down`;
  `up` once more with the room and records back.
- A `down` after an `up` broken off in its second play leaves the host as `down` promises, and names nothing as
  failed that was never there.
- The JSON lines of a run name every step once, and the stop's line names the commands of the person's step.

## To be checked

- With Agent Frontend, whose Dart package is `host up` and `host down`: the callback's file and its fields, the exit
  code for the stop, and how the tarball and the inventory reach the host, as the contract between this collection
  and that package.
- What porelo-frontend's package met on a fresh Ubuntu 26.04, to hold in the plays too: its `sudo` is sudo-rs, which
  ignores `-E`, so an environment goes through `sudo env …`; Ansible refuses a locale that is not UTF-8, so the plays
  run under `C.UTF-8`; and a fresh image has no apt lists while cloud-init may still hold apt's lock.
