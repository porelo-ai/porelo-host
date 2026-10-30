# HO66 — The Forge's Links Reach The Laptop

**Status:** Idea.

**What must be true.** Every link the host's forge gives, such as the hint after a push, opens from a developer's
laptop through the VPN.

## Why

Walk 23 step 10-1: the push hint's link lacked `:3000`. `forgejo.container.j2` sets
`ROOT_URL=https://<forge_name>/`, port 443, while the walk reached the forge on port 3000.

## To be checked

- Whether port 443 answers from the laptop through the VPN on a rented host, as Molecule's test peer shows; if it
  does, what made the walk take 3000, and if not, which of the two ports `ROOT_URL` should name.
