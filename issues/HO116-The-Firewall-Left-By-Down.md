# HO116 — The Firewall Left By Down

**Status:** Idea.

**What must be true.** After `down` a host holds no firewall of the collection's, or a host admin can read why it stays.

## Why

A run of `up` and `down` on a given server left `/etc/porelo-host/firewall.nft`, and it is the only thing `ls` showed in that
directory. No task of `down` names the file or `porelo-host-firewall.service`, which `up` installs and enables, in `v0.5.9`
too. So by reading, the unit stays with it and loads these rules at the next boot; the run did not look at the unit or at
the loaded rules.

Nothing says this is meant, and either answer has a cost. Rules left behind keep ports shut for what a person puts on the
server afterwards. Taking them off opens a server that was shut, which a server given back to its provider does not care
about and one kept does.

## Acceptance

- Which of the two is wanted is decided and written down.
- A run of `down` in Molecule shows that decision: the file, the unit and the loaded rules gone, or standing as written.
