# HO29 — The Person's Own Web Login On The Forge

**Status:** Backlog.
**Size:** S - one task file of the role `forge`, its removal at `down`, Molecule's checks and the documentation; no
contract other repositories read.

Analyzed for porelo-project [PJ61](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj61)'s
sprint 5, whose approval is the person merging a pull request in Forgejo's interface.

**What must be true.** The person signs in to the host's forge in a browser, through the VPN, with an account of their
own, and sees the organization's private repositories, their runs and the registry's packages there. Its password
passes through no inventory, variable, log or task's output, as every other credential of the forge.

## Plan

- The person's forge login is `operator`, the role default `forge_person`, the same on every host. Forgejo refuses
  `admin` as a reserved name (measured on the pinned image), and the role's own accounts are `porelo-admin`,
  `porelo-publisher` and `agent-<name>`, in the namespace Forgejo's users share with the organization `porelo`.
- `roles/forge/tasks/person.yml`, after `repositories.yml`, since the organization is made there:
  - the user is made by Forgejo's command line with `--random-password --must-change-password=true`, only while it is
    missing. That command prints the password inside a sentence, so the shell pipes its output through `sed` straight
    into `/etc/porelo-host/forge/person.password`, root's, `0600`; the password is never a variable, a register or a
    task's output, and the task carries `no_log`;
  - where the organization exists, the user becomes a member of its `Owners` team, so it sees and merges every
    repository there;
  - at the first sign-in Forgejo makes the person set their own password, after which the file's is worth nothing.
- The person fetches the file over ssh straight into a file only they read, as with the agents' tokens, and deletes it
  after the first sign-in.
- `down` removes the file with the rest of `/etc/porelo-host/forge/`.
- `doc/local-forge.md` says how the person signs in, in place of "No person has a password for the forge's web pages".
  `roles/forge/README.md` names `forge_person` and the file.

## Acceptance

- In Molecule's verify:
  - `operator` exists, is in the organization's `Owners` team, and must change its password;
  - the file is root's and `0600`;
  - a sign-in with the file's password, sent to `curl` on standard input under `no_log`, is answered with the
    change-password page;
  - the password itself, searched with `grep -F -f` as the drive's key and the vault's passphrase are, is in no `-vvv`
    output or journal line; `operator` and its file are deleted before the `-vvv` `up`, so that run makes them again.
- Each is seen red without `person.yml`, and the search is seen red on a planted password.
- After `down` the file is gone.

## Decided

- **QH31 (a):** Forgejo generates the first password; it lies in a root-only file on the host until the person fetches
  it over ssh, and the first sign-in replaces it.
- **QH32:** the login is `operator`, the same on every host.
