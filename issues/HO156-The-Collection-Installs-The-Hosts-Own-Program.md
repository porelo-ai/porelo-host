# HO156 — The Collection Installs The Host's Own Program

```json
{
  "$schema": "issue-1.json",
  "id": "HO156",
  "title": "The Collection Installs The Host's Own Program",
  "state": "Review",
  "size": "L",
  "priority": "Medium",
  "rank": 3,
  "blockedBy": [],
  "covers": "The host runs its admin work, gates, judge and pool through the installed `porelo-host` at the pinned version; the collection's scripts go, but for the stated exceptions."
}
```

**Why this size.** every role that installs or calls a host script changes, with its units, the sudo rules, `down`, the
docs and the tests; no new logic, but it crosses into another repository's package.

**What must be true.** A host set up by `up` runs its admin work, its gates, its push judge and its VM pool through the
one installed program `porelo-host` at the version the collection pins. None of the collection's own scripts are
installed on the host any more, except the stated exceptions: the forge's pre-receive hook, the check before
installation, the measuring run and a pool VM's give-back.

## Plan

- **The package.** The porelo role installs `porelo-host` from the same channel as `porelo`, at the version the
  collection names. `up` refuses an older one, naming both versions.
- **Units and sudo rules call the program.** They stay in Ansible:
  - `porelo-host-follow.service`: `porelo-host org follow`;
  - `porelo-host-task-sweep.service`: `porelo-host task sweep`;
  - `porelo-host-verify@.service`: `porelo-host judge-push`;
  - `porelo-forge-{web,git,runner}@.service`: `porelo-host forge gate --web|--git|--runner --upstream <socket>`;
  - `porelo-pool-revert.service`: `porelo-host pool revert`;
  - the vm_pool role's VM steps: `porelo-host pool make|address|delete`;
  - `person.yml`'s runtime step: `porelo-host org follow`;
  - `down`'s central check: `porelo-host project check-central`.
- **sudoers for `%porelo-people`** names exactly five rules:
  - `porelo-host forge issue-token`
  - `porelo-host forge lend-token`
  - `porelo-host task start *`
  - `porelo-host task end *`
  - `porelo-host task show *`

  Each task verb has its own line; the forge verbs take no arguments. Command defaults set `env_reset`, `!setenv`
  and `!env_keep`. Units calling the host program set no extra environment variables or environment files.

  The `arrivals` rule goes: the follow publishes arrivals as a file with a read ACL.
- **The scripts go**, from `roles/*/files/` and from the host at `up` and `down`:
  - `porelo-host-person` and `porelo-host-project`;
  - `porelo-forge-gate`;
  - `porelo-host-push`, `porelo-host-forge-token` with its `.sh`, and `porelo-host-stop`;
  - `porelo-pool-revert`.
- **What stays, and where:**
  - `porelo-vm` moves to `build/`: a development tool for Molecule and the rehearsal, no longer installed.
  - The exceptions in `AGENTS.md` are corrected to what stays: the pre-receive hook, `porelo-host-check`,
    `porelo-host-measure`, `porelo-pool-give-back` and the build scripts.
- **Tests.** The collection's Python tests of the scripts that go are deleted. Their harms are held by `host/`'s JUnit
  tests in porelo. The collection keeps the tests of the roles' YAML and of what stays.
- **Red first.** One guard reads every role's tasks and fails while any role copies a file to the host that is not a
  stated exception, and while the sudoers file names any rule but the five. It also guards the units' and sudoers'
  environment boundary.
- **Docs.** `doc/local-forge.md` and the roles' READMEs name the `porelo-host` verbs instead of the scripts.

## Acceptance

- The guard above, seen red before the change and green after.
- Molecule's default and pool scenarios pass on the package (built by its own issue): the follow act, the gate
  sockets, the judge's refusals, a task's own branch, the pool's revert.
- On a host after `up`:
  - `porelo-host --version` is the pinned one;
  - `ls /usr/local/sbin /usr/local/libexec /usr/local/bin` shows none of the scripts that went;
  - `sudo -l` as a person lists exactly the five rules.

## To be checked

- The host program supplies org follow, refresh and renew-pin; forge gate with --web, --git, --runner and --upstream;
  forge measure; pool make, address, delete, give-back and revert with --one; and judge-push, which
  `porelo-host-verify@.service` runs behind its socket. Runtime restoration uses org follow. It has no manual purge
  command. The pin is published snapshot 462 (porelo 7b1517f20) or later, refused before the former programs are
  removed: 462 is the first published with judge-push, socket-started units under systemd 258+ and a task's push of
  its own branch. Local hand-overs are numbered by Core's run and carry `+local.<stamp>`; Molecule and the rehearsal pin
  to the staged package's own version, never to the default.
- The central check `project check-central` requires a project and repository names. Down uses the available
  complete-project `project give-back-check`; the all-ref invocation needs an explicit enumeration contract.
- The host package pin is the complete Debian snapshot version, separate from porelo_version, as Porelo's repository
  publishes it.
- Molecule with the forge on, on snapshot 963 (systemd 259): the first up never ends. Every socket-started host
  program refuses with exit 78, since systemd sets `LISTEN_PIDFDID` and, per connection, `SO_COOKIE`. Fixed in
  snapshot 964.
- Molecule with the forge on, on snapshot 964: syntax, converge and idempotence pass; verify fails in the follow act,
  since the push judge refuses a task its own branch (`porelo/<task>`): the host program's task record names no
  project, and the judge takes only the tasks of the push's project. Handed to Core, fixed in porelo c2d0f7fe4.
- Review findings have red reproductions and focused passing fixes: an upgrade retains active legacy program targets
  before the unresolved forge refusal; expected follow refusals are accepted; fixture installation and execution share
  restoration. The copied-script source guard remains covered.
- Molecule with the forge off, on the package's snapshot: syntax, converge, idempotence and verify pass, the follow's
  93 facts among them; side_effect stops at down, which refuses while hostadmin holds its host-admin membership, since
  the scenario cannot purge it until the host program has a person purge. The follow act expected a project's
  `.allowed` with the forge off, where the host program writes it only with a forge; seen red before the fix, green
  after.
- The scenario held tasks that never ran, named after another repository's issue, for what the host program lacked:
  the desktop's need interaction and the person purge. They are gone; the person purge stays open above.
- Molecule with the forge on, on Core's local hand-over of porelo b7c5f2de5 (`0.5.1~snapshot.461+local.20261110T084038`,
  package and program of one stamp): a hand-over whose package and program stamps differed was refused before up. The
  host program's environment allowlist refused the down's `ANSIBLE_STDOUT_CALLBACK` with exit 78: every task now calls
  it under `env -i` with a fixed `PATH`, held by a unit test over every playbook and role, seen red first. Then syntax,
  converge, idempotence and verify pass; on the VM `/etc/sudoers.d/porelo-host-person` is the only rule file, and none
  of the former scripts nor `porelo-vm` is installed. side_effect stops at down on hostadmin's membership, as above,
  until the host program has a person purge.
- main's first build with this issue went red in both Molecule jobs: GitHub's runner has no local hand-over, and
  Molecule refuses without `PORELO_HOST_DEB`. The job now fetches the pinned published `porelo-host` and `porelo` of
  snapshot 462, signed by the pinned key, with `build/fetch-host-deb.sh`; a unit test over the workflow, seen red on
  main's, holds it.
- Main's Molecule jobs then stopped at side_effect's down on hostadmin's host-admin membership: the package's purge
  takes only a person seven days gone, and an organization cannot leave its host admin, so down refused on every
  followed host. The operator chose (2026-11-10) that down does not count the host-admin membership; any other
  membership still stops it. The down test that held the old rule was turned round, seen red first.
- With the forge off, the pool's down asked the host program to withdraw the run key from the forge, which refuses on
  a host whose forge.conf names no account: the task's `removes:` held while the old helper came with the forge alone,
  and the package's program is always there. It now asks only when forge.conf names an account; a unit test, seen red
  first, holds it.
- The host's part of the acceptance, on a VM after `up` (rented-mode run with phase 2 from main af4704c, snapshot
  474, 2026-11-10 22:49-22:56Z), read at the run's hold:
  - `porelo-host --version` answers `porelo-host 0.5.1~snapshot.474`, the staged package's own version;
  - `/usr/local/sbin` and `/usr/local/bin` are empty; `/usr/local/libexec/porelo` holds only `pre-receive`, a stated
    exception; `/etc/sudoers.d` holds `porelo-host-person` beside cloud-init's own;
  - `sudo -n -l` as the test person lists exactly the five rules, each `(root) NOPASSWD:` on
    `/usr/sbin/porelo-host`: `forge issue-token`, `forge lend-token`, `task start *`, `task end *`, `task show *`;
  - the run then went down cleanly after taking the project off and the host out of the organization.
- Molecule's default scenario with the pool on, on snapshot 474 (main c50ab3f with this record, 2026-11-10
  23:18-23:46Z): syntax, converge, idempotence, verify and side_effect pass; the pool's revert ran, normal and killed
  renters left nothing, and the real acceptance leg passed and was removed; the run removed its VM. With main's build
  of c50ab3f, whose Molecule job runs the default scenario with the pool off on snapshot 462, both scenarios pass on
  the package.
