# HO26 — Each Agent's Own Forge Account

**Status:** Review.
**Size:** S - one task file of the role `forge` and its Molecule checks; the token never leaves a root-only file on
the host.

**What must be true.** Each agent the host's settings name pushes to the host's forge as an account of its own, with a
token that may write the organization's repositories and nothing of the central forge, and that is never shown,
logged or written anywhere but a file only root on the host reads.

## Plan

- `porelo_host_forge_agents`, a list of names (`^[a-z][a-z0-9-]{0,30}$`, unique, default `[]`), beside
  `porelo_host_forge_repositories` in the inventory; the role's `forge_agents`.
- `roles/forge/tasks/agents.yml`, after `publisher.yml` where repositories are configured: a user `agent-<name>` by
  Forgejo's command line, a team `agents` in `forge_owner`'s organization that writes code, pulls and issues on all its
  repositories and reads actions and packages, each agent a member; a token with
  `write:repository,read:package,read:organization` written by the shell into
  `/etc/porelo-host/forge/agents/<name>.token`, root's, `0600`, its directory `0700`, made only when the file is
  missing. A name taken off the list keeps its account and token: absence deletes nothing.
- `down` removes the directory with the rest of the forge's files.
- The operator copies each token over ssh straight into a file on their computer that only its owner reads.

## Acceptance

- Molecule with the forge: `agent-probe` is in team `agents`; its token's file is root's, `0600`, in a `0700`
  directory; a clone pushes a branch to `porelo/stand-in` with it and is refused on `central/stand-in`; the file is
  the same after the second and the `-vvv` `up`; the token's digest is in no `-vvv` output, journal line or task
  container.
- After `down`, the directory is gone.

## Decided

- **QH28 (a):** the agents' accounts are a task of the role, not typed by hand (the operator's decision).

## Built

- `roles/forge/tasks/agents.yml` as planned, run after `publisher.yml`; the names are checked before any reaches a
  command or a path, and every task near a token carries `no_log`.
- **Molecule with the forge**, green on the code of this commit, 2026-10-25 16:56Z-17:10Z, 5/5 stages, the VM
  removed: `agent-probe` is in team `agents`; its file is root's, `0600`, in a `0700` directory; a clone pushes a
  branch to `porelo/stand-in` with its token and is refused on `central/stand-in`; the file's digest is the same after
  the second and the `-vvv` `up`; the token's digest is in no `-vvv` output, journal line or task container.
- Seen red first only with fixtures outside the VM: without the token file and with the central push allowed, the same
  assertions fail; a planted token fails the digest search. A VM run without `agents.yml` was not made.
