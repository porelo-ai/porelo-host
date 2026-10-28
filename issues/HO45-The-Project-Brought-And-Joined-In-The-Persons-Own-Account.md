# HO45 — The Project Brought And Joined In The Person's Own Account

**Status:** Analyzed (Accepted by the operator, 2026-10-28; estimated by its agent, for the operator to set Estimated).
**Size:** L - two playbooks run as the person, the stop's own-account mode, the setup's files in the person's home
with two bundles, and the forge's per-project parts with the person's own token.

**What must be true.** A project admin brings their project onto the host, and a developer joins it, each in their own
account with no root: Porelo follows the project and its access file, the keys and tokens go into their own vault, and
the forge's parts of the project are made with the admin's own forge token.

## Why

[PJ78](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj78): Porelo runs only in a person's own account; the project admin brings, the developer works.

## Plan

- **The stop's own-account mode:** `porelo-host-stop --stdin`, run without `sudo`, acts on the caller's own account:
  `vault-new`, `vault`, `keys`, `forge-central-token` into `$XDG_RUNTIME_DIR/porelo-host/`, and `identities` from the
  `/run` file of [HO43](README.md#ho43). It refuses `wireguard` and `forge-certificate`; the root stop refuses the rest.
- **The setup's files** ([HO36](README.md#ho36)'s checks): the machine file and two bundles, the project's and the
  access repository's, in the person's own home, the person's own and not writable by others.
- **`playbooks/bring.yml`** (`-c local`, as the project admin): follow with both bundles; the project's keys; with
  their own forge token the repositories migrated (`forge-central-token` used in that process only), `main` protected
  (fast-forward only, an approval from `Owners` or `developers`, QH61 b), the teams `developers`, `gates` and
  `agents`, the organization's Actions variables; the push config in `~/.config/porelo-host/push/<project>.conf`; one
  `sync` ([HO46](README.md#ho46)) at the end.
- **`playbooks/join.yml`** (as the developer): follow with both bundles, the keys, the identities' tokens, their own
  forge write token, the push config. No forge change.

## Acceptance

- Molecule: the bring and the join end green as their own users with no `sudo` but `sync`; the protection asks an
  approval from either team; the person's vault holds the tokens and no file outside it does; a setup file another
  user can write is refused, naming it.

## To be checked

- porelo's access file and inventory with two bundles (porelo's issues for [PJ78](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj78)).
