# HO46 — The Developers Kept In Step With The Signed Access File

**Status:** Review.
**Size:** L - root verifying through Porelo's own check as a throwaway user, the `host:` check, the whole diff
checked before acting, add and lock per laptop, and the project admin's timer.

**What must be true.** The developers on the host are exactly those the project's signed `access.yml` names: a
developer listed is admitted, one dropped is locked at once, and nobody the signer did not list can be admitted, not
even from a taken-over project admin account.

## Why

Developers are listed with their public keys in the signed file, kept private in
`access.yml` (b).

## Plan

- **`sudo -n porelo-host-person sync <project>`**, run by the project admin's user timer after each applied commit of
  either repository, and once at the end of `bring.yml`:
  1. root copies both bundles into a root-only directory;
  2. it runs `systemd-run --pipe --wait -p DynamicUser=yes -p PrivateNetwork=yes -p ProtectHome=yes porelo project
     verify --repository <copy> --access-repository <copy> --signed-by <pinned> --since <c> --access-since <c> --json`
     and reads only the JSON;
  3. `host:` must name this host's network, WireGuard key and CA SHA-256, or nobody is admitted;
  4. the whole diff against `people/` is checked before anything is done (the refusals of
     [HO43](README.md#ho43)); one refusal refuses all and names each entry;
  5. developers and laptops added (QF76 a) as in [HO43](README.md#ho43); dropped ones locked at once (QH65 a), under
     the memberships of [HO55](README.md#ho55) (operator's decision, room 2026-10-29): `sync` adds or removes only
     this project's membership, and a person is locked only when no membership is left. It never undoes an admission
     by hand. A developer in two projects keeps access through the other when dropped from one; a developer listed
     who already has an account, admitted by hand or from another project, gets this project's membership added, not
     a second account;
  6. both commits recorded, so an unchanged run does nothing and says so.
- `forge_login` in the JSON is passed by.
- After `sync` the timer runs Matrix's `members` through the admin's own Porelo.

## Acceptance

- Molecule: a signed list changed twice: one developer with two laptops added; one laptop dropped (that laptop locked
  alone); one developer dropped (locked); a developer in two projects dropped from one keeps access; a listed person
  admitted by hand gets the membership, no second account, and keeps access when dropped; a list signed by another key, a `host:` of another host, and an address
  taken by another person each refused with nothing changed.

## To be checked

- porelo's `project verify --json` with `--access-repository`, and that it runs under
  `DynamicUser` with no home and no network.
