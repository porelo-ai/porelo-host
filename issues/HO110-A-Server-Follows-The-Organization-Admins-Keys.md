# HO110 — A Server Follows The Organization Admins' Keys

**Status:** Review.
**Size:** S - one optional list read and checked in the follow, the pin written from two lists, the documents.

**What must be true.** A server's pin holds the keys of the organization's Organization Admins beside its own Machine
Admins, so a Machine Admin changed or replaced by an Organization Admin takes effect on a running server at its next
follow, with no confirmation by the former admin, who may be gone. Taking that list needs no person on the server, and
it makes no account for anyone on it. A Machine Admin names no further Machine Admin; that is the Organization Admin's
alone, so a list a Machine Admin alone has changed is not taken. One stolen key of this role reaches every server; that
is known and decided.

## Plan

- `org fetch` answers `organization_admins` beside `admins`, rows of `login`, `key`, `fingerprint` and `backup`, absent
  from a build older than the list. `follow_state` checks it, and any malformed row refuses the state with nothing changed.
- `write_follow_pin` writes the pin from the machine's admins first, then the role's keys not already held, one line a key.
  The machine's admins stay first, as `org status`'s `pinned` and the forge's owner read the first.
- **Root, decided:** root's key file reads `admins` alone. An Organization Admin who needs root lists themselves as that
  machine's Machine Admin, a visible signed change, one server at a time. A stolen key of this role can do the same,
  visibly; that cost is accepted.
- The memberships keep reading `admins` alone, so the role gets no account and its logins need not be among `persons`.
- **A server already set up, and a new one:** both take the list at their next follow, as adding it moves no pin by
  itself; Porelo judges a pin's move by the list as it stood before that commit. `up` and its machine file do not change.
  An owner not listed still moves no pin and leaves the host refusing.
- **An older helper** writes the pin from `admins` alone, so a change only the role signed is refused and said; it does
  not read wrongly.
- Red first: both lists in the pin and only one in root's file; a list arriving on a running server; a list emptied or
  gone; a person in both lists; a machine admin replaced; each malformed row.

## Acceptance

- The tests above, seen failing without the change, and Molecule's follow unchanged with no list.

## A server with no Machine Admin left

Porelo's `org host admin remove` keeps the last admin, but a machine's only admin who withdrew or lost their card can
leave `admins` empty. The host refuses that state and keeps the last it took, and an Organization Admin ends it by adding
a new admin. Agent Core read this and did not run it.
