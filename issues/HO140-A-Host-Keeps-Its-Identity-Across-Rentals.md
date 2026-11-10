# HO140 — A Host Keeps Its Identity Across Rentals

```json
{
  "$schema": "issue-1.json",
  "id": "HO140",
  "title": "A Host Keeps Its Identity Across Rentals",
  "state": "Idea",
  "size": "-",
  "priority": "Medium",
  "rank": 5,
  "blockedBy": [],
  "covers": "A host rented again and again keeps its read keys from the person's vault, so they stay registered between rentals and only a host given up for good has them removed."
}
```

**What must be true.** A host rented for a few hours at a time is set up anew each time, but to the organization it stays
the same host. Its read keys are the same from one rental to the next, as on a host that runs for good, and stay
registered at the central forge between rentals, so nothing is left to remove by hand after a rental. The keys are kept
encrypted in the person's vault and brought onto each new rental by its preparation. `up` and the follow use them
instead of making new ones. Only a host given up for good has its read keys removed.

## Why

Today every setup makes new read keys. A rental's keys stay able to read at the central forge until the repositories'
owner removes them, and a host rented again adds new keys beside them.

## To be checked

- **The organization's read key:** `roles/porelo/tasks/organization.yml` makes
  `/etc/porelo-host/organization/read/organization` once, with `ssh-keygen`, when the file is missing. Porelo titles its
  deploy key by the key's fingerprint, so a new rental adds a second key beside the first. The fix would be to take a
  key brought by the preparation, with the same checks as today (a root-owned plain 0600 file), and make one only when
  none is brought.
- **A repository's read key:** `porelo-host-project migrate` makes one key a repository in
  `/etc/porelo-host/organization/read/projects/<project>/` and registers it under the title
  `porelo host <host> project <project>`. Given the central token, it already deletes an earlier key of the same title
  but a different public half. A rental with the same host name therefore replaces its predecessor's key, at the cost of
  needing the token on every rental, and one with another name leaves the old key. Read whether a key that is carried
  over makes the migration find its key already registered and skip the token.
- **How the preparation carries them:** what kind and name the vault entry has, one for the host's set of keys or one per
  key, and how the window reads it and puts it on the host as root. The keys travel the way the stop's secrets do today,
  on standard input, never in an inventory, a variable, a log or a command line. What Porelo's vault offers for such an
  entry, and what the interface stores.
- **Which identity is meant:** whether the host's own SSH host keys belong to it too. The window pins them per rental from
  the provider's tag today, and keeping them would let a person's known hosts stay valid.
- **Given up for good:** which command says a host is given up, as opposed to given back after a rental. That command
  removes the read keys at the central forge and deletes the vault entry. `down` after a rental keeps both.
- **[HO114](README.md#ho114):** for a rental, this makes the removal at `down` unneeded. That issue is still needed for a host
  given up for good. Either it narrows to that case, or this issue takes it in.
- The keys of rentals made before this is built are removed by hand once it is in place.
