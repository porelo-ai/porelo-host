# HO55 — A Person Leaves When No Membership Is Left

**Status:** Analyzed; blocked by [HO43](README.md#ho43), [HO44](README.md#ho44).
**Size:** M - the person record's memberships, `porelo-host-project remove` locking whom it leaves with none, `down`'s
refusal, their tests and a Molecule act.

**What must be true.** Every person on the host is there by a membership, and leaves when none is left. `down` never
leaves an admitted person behind: it refuses while anyone holds a membership, naming each.

## Plan

- **The decision** (operator's, relayed by the Coordinator in the room, 2026-10-29, answering what `down` does with
  admitted people):
  1. Every person carries memberships: per project, as project admin or developer, and "admitted by hand" when the
     host admin admitted them.
  2. A project's `sync` adds or removes only that project's membership ([HO46](README.md#ho46) holds this).
  3. `porelo-host-project remove <project>` drops that project's memberships; whoever then has none is locked.
  4. `down` refuses while anyone holds a membership, naming each; the way back is *Take the project off* and *Purge*.
- **The record:** `people/<user>.conf` holds the memberships in place of today's `role=` and `projects=`: one line
  per membership, `member=hand` or `member=<project> project-admin|developer`. `porelo-host-person add` records
  `member=hand`; `porelo-host-project add` adds the admin's membership of the project. A record from 6j, with
  `role=project-admin` and no member line, is read as admitted by hand.
- **`remove <project>`:** after the forge's parts, the project's membership leaves every record under the same lock;
  each person left with none is locked as `lock` does, and the answer names them. A person still admitted by hand or
  in another project keeps access.
- **Purge** drops every membership; `lock` keeps them, so a locked person is still named by `down`.
- **`down`:** a first step reads `/etc/porelo-host/people/` and refuses, before anything is stopped, while any record
  holds a membership, naming each person and their memberships, with the way back in the words of the interface.
- **Tests first:** the record's memberships read and written, a 6j record read as admitted by hand; `remove` locking
  only those left with none; `down` refusing with names and stopping nothing. Each red before the change.

## Acceptance

- Molecule: a person admitted by hand and made a project's admin keeps access when the project is removed; one only
  in that project is locked by the removal; `down` refuses while a person holds a membership, names them, and goes
  through once they are purged.

## To be checked

- How the interface shows `down`'s refusal and the two ways back; the words are its own.
