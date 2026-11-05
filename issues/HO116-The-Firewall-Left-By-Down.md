# HO116 — The Firewall Left By Down

**Status:** Review.

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

## Decided

**`down` leaves the firewall on, and says so, with the command that takes it off.** A machine kept after `down` should not become open by a step whose name promises a clean-up: the next service
anyone starts would be exposed unasked, and a person who wanted it open can do that in one line. The other recommendation, taking it off, goes to the operator beside this one in the morning.

## Result

The rules name no service, only ssh and the public interfaces, so a reload holds with the services gone. `down` ends with a `note` line of the callback, which a reader not knowing it skips. Molecule's
`down` asserts the unit, the loaded rules, the file and the note, and then runs the note's command and sees the rules gone.
