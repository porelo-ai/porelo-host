# HO02 — Porelo's Own Commands Called, Never Redone

**Status:** Implementing.
**Size:** L - one role here, but it rests on a contract with `porelo` that does not exist yet, and `up` is cut in two
by a step the person takes by hand.

**What must be true.** On the host, the playbook installs Porelo's package, makes the account and runs `porelo
setup`, deposits the keys, follows the project and starts its tasks, each only through Porelo's own commands. No key,
token or passphrase passes through the inventory, a variable, a fact, a register or a task's output, and a second
run changes nothing that is already as it should be.

## Plan

- **One role, `porelo`**, its components as task files in the order [PJ40](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj40) sets: `install.yml` (the package by
  `porelo-setup-latest.sh --user <account>`, which is idempotent and exits 0 when it is already so), `account.yml`,
  `setup.yml` (`porelo setup`, safe to re-run, which skips the vault without a terminal), `keys.yml`, `follow.yml`,
  `tasks.yml`.
- **Decided: a person opens the vault.** The first play ends after `porelo setup`, saying what to run: `ssh -t <host>
  porelo vault init` on a fresh host, `porelo vault unlock` otherwise. The second play checks first that the vault
  is open and stops, naming that step, when it is not; then it deposits the keys, follows and starts. A vault opened
  with nobody there is [HO10](README.md#ho10). At `down`, `porelo vault clear --yes` removes the keys from the host, after the copies [HO09](README.md#ho09)
  orders before it, since on an account with its own homeserver it removes the homeserver's database too. Everything as the account,
  through `become_user`, never as root after the install.
- **What the plays read is written for them, in two parts** (decided): porelo-frontend's `host up` writes the first
  play's variables - the account, the packages - since no Porelo runs before the host exists; Porelo on the host
  writes the second play's after `porelo setup`, from `project.yml` and the person's machine file on the drive - the
  project's name and URL, the signing key's fingerprint, the tasks to start, the keys as names and drive paths. The
  role validates both by `meta/argument_specs.yml` and never reads `project.yml` itself.
- **The keys go from the drive into the vault on the host**: for each key the inventory names (a name and a path on
  the person's mounted drive), the task runs `porelo vault put <name> < <path>` on the host, so the value goes from a
  file into Porelo's standard input and never through Ansible; `no_log: true` on it all the same.
- **Follow and start**: `porelo project follow <name> <url> --signed-by=<key>`, never `--unverified`; then `porelo task
  start <task> -p <project> -r <repository> --detach --no-input` for each task the inventory names. Whether a task
  already runs is read from Porelo, not from a file of the role's, so a second run starts nothing twice: on a running
  task this start says "is already running" and exits 65, before it looks at the options, which porelo's
  `TaskRunCommandTest` holds.
- **`changed_when` and `failed_when` from what Porelo says**: an exit code or a line Porelo documents for "already so",
  never a guess; where Porelo has no such answer, it is asked for in the `porelo` issue, not worked around here.
- **Red first**: a key's value written into a task's output or into the run's log, seen by a test that greps the
  whole `ansible-playbook -vvv` output for a planted value, and fails; then the tasks as above, and the test green.

## Acceptance

- On the test VM `build/molecule.sh` makes: after `up`, `porelo doctor` passes as the account, the project is
  followed with its signature checked, and the named tasks run.
- A second `up` reports `changed=0` for this role.
- A planted key's value appears nowhere in `ansible-playbook -vvv`'s output, the host's journal, or Ansible's facts
  cache.
- The second play on a shut vault stops before it deposits anything, naming `porelo vault unlock`; after `down`,
  `porelo vault list` as the account shows no key.
- A project file whose signature does not check stops the run with Porelo's own refusal, and no task is started.

## Decided

- **QH19 (d), 2026-10-19:** the setup script comes as a package, `porelo-setup`, from Porelo's apt repository, which
  the role adds by the fingerprint porelo's `getting-started.md` pins; Ubuntu first. Until that package is published,
  the Molecule scenario stands in for the script by that repository and `apt install porelo`.

## Built

- The role `porelo`'s first part, in `up`'s first play after the drive: `porelo setup` as the account (changed only
  when its daemon line says `started`, since it writes its hooks on every run), then `porelo vault status`, adding
  `vault-new` (4) or `vault` (3) to `porelo_host_needs`. Molecule: the first `up` stops with
  `needs: ["drive", "vault-new"]`; after the person's step, `porelo vault init --passphrase-stdin` as the account, the
  next `up` runs through, `porelo doctor` passes, and idempotence reports `changed=0`. Seen red first: without the role
  the first `up` named `drive` alone.

- `install.yml`, run as root before `base`'s account step: Porelo's key fetched and installed only with the pinned
  fingerprint, its source line for `porelo_distribution` (from `porelo_host_distribution`, `releases` by default;
  porelo [B208](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b208)'s `vault status` is in the
  snapshots only so far), `apt install porelo`, then the setup script at the path
  porelo's package will hold it (porelo's "The Setup Script Shipped As A Package"), changed only when its "already" lines are not all there. Molecule stands in for
  the packaged script with the newest snapshot's published one.
- **On the development host at Scaleway** (`195.154.103.106`, 2026-10-19, collection from the working tree): the three
  steps made the account; `base`'s account step passed; the drive came up with Tresorit's real installer checked and
  its daemon running; `porelo setup` ran; `up` stopped with `needs: ["drive", "vault-new"]`, and after a throwaway
  `vault init --passphrase-stdin` with `needs: ["drive"]` alone. A second `up` changed nothing else. `down` from the
  stop ended 0: VPN stopped, daemon stopped, drive unmounted.

- `project.yml`, in `up`'s second play after the VPN: `porelo project inventory --machine-file` (the machine file at
  `porelo-host/machine.yml` on the drive), refused with Porelo's own words on 66 or 65, its version checked; each key
  put by `porelo vault put --from-file` under `no_log`, only while its name is missing from `vault list`, since
  `put` cannot say unchanged yet, so a key the person changes on the drive is put again by hand until it can; the
  project followed with `--signed-by` the machine file's fingerprint only where `following --json` differs. Molecule:
  a project of the run's own in a local repository, its commit signed by a key of the run's, is followed `verified`
  and `applied`, its key is in the vault, idempotence `changed=0`. Seen red first without the part.
- **On the development host:** the same with a throwaway signed project: followed and applied, the key in the vault,
  a second run following nothing again; a machine file naming another key stopped the part with Porelo's 65,
  "signed by …, not by … Nothing was pinned. No inventory was written.", before any key or follow.

## Measured

In a VM of `build/molecule.sh`'s, Ubuntu 26.04, porelo `0.5.1~snapshot.312`:
- `porelo-setup-latest.sh --user <account> --distribution snapshots` gives rc 0 twice, the account with linger and
  subordinate ids; `porelo setup` with no terminal gives rc 0 and "vault none yet".
- `vault status` 4, then 0 after `vault init --passphrase-stdin`, 3 after `lock`, 0 after `unlock --passphrase-stdin`.
- `project inventory --machine-file <missing>` 66; `project following --json` `{"follows":[]}`; `task status <none>
  --json` `"state":"absent"`, rc 0. `following --json`'s `signed_by` lists fingerprints, which the machine file's
  `signed_by` is compared with.
- `vault put --from-file=<path>` reads the key on the host itself. It says `stored` again for the same value, so a
  `put` cannot yet report "unchanged"; porelo's Idea for that is Core's.

## To be checked

- `porelo-setup` as a package, once published: its name, and that the script runs from it as from the download.
- That the role adds `vault-new` (no vault, `porelo vault status` 4) or `vault` (shut, 3) to `porelo_host_needs` in
  `up`'s first play, so its second play stops with the waiting line `doc/lines.md` describes; [HO09](README.md#ho09) built that stop and
  leaves its acceptance here.
