# HO156 — The Collection Installs The Host's Own Program

**Status:** Backlog; blocked until porelo publishes the `porelo-host` package with every verb below.
**Size:** L - every role that installs or calls a host script changes, with its units, the sudo rules, `down`, the
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
  - `porelo-forge-{web,git,runner}@.service`: `porelo-host gate forge --web|--git|--runner`;
  - `porelo-pool-revert.service`: `porelo-host pool revert`;
  - the vm_pool role's VM steps: `porelo-host pool make-vm|find-vm|delete-vm`;
  - `person.yml`'s runtime step: `porelo-host person restore-runtime`;
  - `down`'s central check: `porelo-host project check-central`.
- **sudoers for `%porelo-people`** names exactly three rules:
  - `porelo-host forge issue-token`
  - `porelo-host forge lend-token`
  - `porelo-host task *`

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
  stated exception, and while the sudoers file names any rule but the three. Today it fails on all of them.
- **Docs.** `doc/local-forge.md` and the roles' READMEs name the `porelo-host` verbs instead of the scripts.

## Acceptance

- The guard above, seen red before the change and green after.
- Molecule's default and pool scenarios pass on the package (built by its own issue): the follow act, the gate
  sockets, the judge's refusals, a task's own branch, the pool's revert.
- On a host after `up`:
  - `porelo-host --version` is the pinned one;
  - `ls /usr/local/sbin /usr/local/libexec /usr/local/bin` shows none of the scripts that went;
  - `sudo -l` as a person lists exactly the three rules.
