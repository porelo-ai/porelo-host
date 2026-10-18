# HO02 — Porelo's Own Commands Called, Never Redone

**Status:** Estimated; blocked by porelo [B208](https://github.com/porelo-ai/porelo/blob/main/issues/base/README.md#b208).
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

- On a fresh host ([HO03](README.md#ho03)): after `up`, `porelo doctor` passes as the account, the project is
  followed with its signature checked, and the named tasks run.
- A second `up` reports `changed=0` for this role.
- A planted key's value appears nowhere in `ansible-playbook -vvv`'s output, the host's journal, or Ansible's facts
  cache.
- The second play on a shut vault stops before it deposits anything, naming `porelo vault unlock`; after `down`,
  `porelo vault list` as the account shows no key.
- A project file whose signature does not check stops the run with Porelo's own refusal, and no task is started.

## To be checked

- That `porelo-setup-latest.sh` is fetched with its digest checked, and from where.
