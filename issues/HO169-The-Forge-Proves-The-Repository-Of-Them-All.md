# HO169 — The Forge Proves The Repository Of Them All

```json
{
  "$schema": "issue-1.json",
  "id": "HO169",
  "title": "The Forge Proves The Repository Of Them All",
  "state": "Estimated",
  "size": "S",
  "priority": "Medium",
  "rank": 6,
  "blockedBy": [],
  "covers": "porelo-host's Molecule scenario and rehearsal prove `porelo-all` on the host's forge: a private repository the follow makes, its `main` taken only from its rebuild identity, that identity unable to write any other repository, and its rebuild workflow run by the forge's runner."
}
```

**Why this size.** It is porelo-host's share of porelo-project's PJ58 (part of ST319): checks and a rehearsal step,
not the forge code. The code that makes forge repositories, protects their `main` and makes identities moved into
porelo's host program (`host/src/main/java/org/fuin/porelo/host/FollowProjects.java`, `ProjectMigration.java`,
`ProjectRegistration.java`). It is no longer in this repository's forge role, so PJ58's step 3 is Core's code. What
stays here:
- the Molecule checks;
- the runner that runs the rebuild workflow, which the forge role already sets up;
- a rehearsal step.

**What must be true.** On a host whose organization's `project.yml` names `porelo-all` with the host's forge as its
upstream:
- the follow leaves a private `porelo-all` in the project's forge organization;
- its `main` takes pushes only from the rebuild's identity;
- that identity reads every repository of the project and can write no other;
- the rebuild workflow from porelo-project's `tools/porelo-all/` runs on the forge's runner and fills `porelo-all`.

The split back and its identity are PJ110, not this issue.

## Plan

1. **Molecule (verify).** It starts with the stand-in organization's project naming `porelo-all`, and these must hold:
   - the repository exists and is private;
   - a push to its `main` as the gate's identity is refused, and one as the rebuild's identity goes through;
   - a push by the rebuild's token to another repository of the project is refused;
   - the token is in `porelo-all`'s action secrets and nowhere else.

   These are seen red until Core's follow makes them, then green.
2. **The runner.** The rebuild workflow runs on the forge's existing runner. The check is that one rebuild job runs
   through it and leaves a commit on `porelo-all`'s `main`. Runner capacity is unchanged: one more job per merge.
3. **Rehearsal.** A step `build/rehearse-steps/porelo-all` checks the same on a rented host: the repository is filled,
   and a task that follows it reads every repository. It exits 77 while the project file names no `porelo-all`.
4. **Docs.** `doc/local-forge.md` names `porelo-all`, its identity and what the follow does with it.

The cost is 27 min at the median for S. It waits on Core's follow change, porelo-project's `tools/porelo-all/` and
the operator's signed `project.yml`.

## On a person's own machine

A person's own machine has no host forge, so there `porelo-all` cannot be a repository on one. A task over every
repository can still read them all, as ST319's discussing task needs, if porelo makes the checkout at the task's
start:
- from the project's repositories that the machine already clones or mirrors, each `main` as a directory, with the
  same `git subtree add --squash` that porelo-project's `rebuild.sh` uses;
- read only, its changes thrown away when the task ends.

That is Core's, in the task start. It needs no forge, no identity and nothing of porelo-host. The rebuild script
should be written so that it runs against local clones as well as the forge's, so both places build the same tree.
