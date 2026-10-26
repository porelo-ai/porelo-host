# HO32 — The Gathered Push Refuses A Moved Central Forge

**Status:** Backlog.
**Size:** M - one command with its install and removal, a measured refusal and its recovery branch, the hidden
token's path, and a Molecule scenario against a stand-in central forge; no contract other repositories read.

**What must be true.** The person sends each repository's approved local `main` from the host's forge to the central
forge with a plain `git push` without force, one repository at a time. When the central forge holds a commit the local
forge lacks, the push of that repository is refused, says which commits, and loses nothing on either forge; those
commits then reach the local forge as a branch to merge. The token for the central forge is asked for each time and
kept nowhere. Starting the push from a task through the broker comes later.

From porelo-project [PJ39](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj39) and
[PJ61](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj61)'s sprint 5, where the person
approves each pull request on the local forge and the central forge receives only what was approved.

## Plan

- **A command on the host, `porelo-host-push <repository>...`**, a shell script, since the host has no Java and the
  person runs it in the ssh terminal as root (`sudo`, which the rented host's login account has). The role `forge`
  installs it as `/usr/local/sbin/porelo-host-push` where `porelo_host_forge` is true, and `down.yml` removes it.
- **Its settings:** the role writes `/etc/porelo-host/forge/push.conf`, root's, `0600`: the local forge's address
  (`https://{{ forge_address }}:{{ forge_http_port }}`), `forge_owner`, and each repository of
  `porelo_host_forge_repositories` with its migration source `url`, which `repositories.yml` already checks to carry no
  credential. It goes with the rest of `/etc/porelo-host/forge/` at `down`.
- **Reading the local forge:** with the forge admin's token from its root-readable file
  (`/home/porelo-forge/.config/porelo-forge/api.token`), the command clones local `main` of each named repository into
  a temporary directory only root reads, removed on exit and on interrupt. Git trusts
  `/home/porelo-forge/tls/ca-bundle.pem`, the system's CAs with the host's, so both the local forge and the central one
  are trusted. It reads no global configuration (`GIT_CONFIG_GLOBAL=/dev/null`) and never prompts
  (`GIT_TERMINAL_PROMPT=0`). A repository not in `push.conf` is refused before anything is read.
- **The central token:** asked once with `read -rs`, never echoed, held in a shell variable only for the run. It
  reaches git only as `http.extraHeader` through `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_0`/`GIT_CONFIG_VALUE_0`, never on a
  command line.
- **The push:** `git push <central> main:main` without force, each repository in the order given, the next only once
  the one before was taken.
- **A moved central forge:**
  - a rejection (`[rejected] … (fetch first)` or `(non-fast-forward)`) stops that repository and every one after it;
  - the command fetches central `main`, names its commits that local `main` lacks
    (`git log --oneline main..FETCH_HEAD`), and pushes them to the local forge as the branch `central/main`, which a
    task merges and the person approves;
  - it exits nonzero, naming the repository and the commits;
  - nothing is forced, so neither forge loses a commit.
- **Output:** what each step did, with every token and its Basic-auth form redacted; git's stderr shown only after
  redaction, as Molecule's `tasks/forge_push.yml` does today.
- **Documentation:** `doc/local-forge.md` describes the command where it now says the gathered push is not built, and
  `AGENTS.md` names `roles/forge/files/porelo-host-push` among the files that cannot be Java, with the reason.

## Acceptance

- In Molecule, against the stand-in central forge on the host (`central/stand-in`), the token given on standard input:
  - a push with nothing new on central is taken, and central `main` holds local `main`'s commit;
  - with a commit A on central, the push is refused, A is still there (`contents/A`, `200`), local `main` is unchanged,
    and `central/main` on the local forge holds A;
  - a repository not in `push.conf` is refused;
  - the token's value is in no output and no journal line;
  - the temporary directory is gone after success, a refusal and an interrupt.
- A forced push in the command's place, and a token on its command line, must each fail these checks.
- After `down`, the command and `push.conf` are gone.

## To be checked

- That a fine-grained token with *Contents* and *Workflows* write is enough to push a commit that changes
  `.github/workflows/`; GitHub refuses that push without *Workflows*.
- That the forge's admin token may push `central/main` while the local forge's `main` is protected
  ([HO31](README.md#ho31)).
