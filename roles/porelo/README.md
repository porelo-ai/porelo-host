# porelo

Porelo's packages and person records on the host: `tasks_from: install` adds Porelo's apt repository by its pinned key,
installs `porelo` (and `porelo-adapter-forgejo`, providing `/usr/libexec/porelo/builds/forgejo`, when
`porelo_host_forge` is true), makes `/etc/porelo-host`, and installs `/usr/local/bin/porelo-host-stop` and `/usr/local/bin/porelo-host-forge-token`
with its helper `/usr/local/share/porelo-host-forge-token.sh`, which `porelo-host-push` shares, running no setup
script for an account. `tasks_from: person` installs `/usr/local/sbin/porelo-host-person` (`purge`, `org follow`,
`org refresh` and `org status`), private return-socket directories with the daemon link
and the `porelo-people` group; the verified organization state lands in
`/etc/porelo-host/organization/applied.json`, see
[the host's state taken from the organization](../../doc/local-forge.md#the-hosts-state-taken-from-the-organization);
`/etc/porelo-host/people/<user>.conf` records each person's `member=host-admin` and `member=<project> project-admin|developer`
memberships, `locked=` state, the one card's `ssh=` key and `expires=`, with an optional lock `reason=`.
`tasks_from: people`
runs at the start of `down` and refuses before
anything is stopped while any record in `/etc/porelo-host/people/` holds a membership, naming each person and their
memberships with `"Take the project off"` and `"Purge"`.

Root's persistent `porelo-host-follow.timer` runs `org follow` every five minutes. It fetches the organization using
the host's deploy key in an isolated unit with network access, reconciles cards and project memberships, and publishes
`organization/projects/<project>.json`, naming the host, with a read ACL for each unlocked member, and `organization/persons/<login>.json`, holding that person's projects as
`{"projects": [...]}`, with a read ACL for that person alone, gone with their last membership, so `porelo project list`
names their projects before a first start there. Accounts with no
membership or host admin role are locked when the host takes the change, within five minutes or at once on `org refresh`, and purged on
the first follow seven days after the recorded lock day; readmission
before then restores the existing account, completing subordinate IDs and linger after an interrupted admission.
Purge deletes the person's Forgejo users and their tokens, including the task gate's user.
A person still listed in a project, locked there or holding a revoked card,
is locked and never purged. A card replaced under another key takes the login back, while the old key stays on the KRL
for good. Nothing is followed until `org refresh`, given the host admin's central token once on
standard input, has had `porelo org add-read-key` add the host's read key; the token is kept nowhere, and until then
`org status` answers `"organization":"waiting-for-token"`. Each follow also compares the projects in the taken
state with the host's project records. With a forge, it registers each new project under an unlocked project admin
and that admin's current signing key. The project stands as `waiting-for-token` until `org refresh` receives the host
admin's central token on standard input and migrates the repository the state names. The token is kept in memory
for that refresh alone. Empty standard input follows immediately without migrating a waiting repository.
A host without a forge admits the members without running a forge command.

Taking a project off runs the project helper's removal after membership revocation. An unpushed commit keeps the
project `held`; `org status` names its repositories and commits, and each follow checks again with root's read-only
deploy keys. A missing key or unavailable comparison keeps the project
and names the failed check. No central write
token is needed for that comparison. A follow that fails part-way has still taken the state: it takes members' read
access away first, and the next follow retries the rest. Root's `0600` `organization/host-projects.json` retains
unfinished registration, migration and room work independently of the accepted revision. Status includes these
projects and each person's scheduled `purge_on` day.

At `up`, the root-owned `0600` machine file's `organization` mapping supplies `settings` (the unparsed text of
`organization.yml`), `known_hosts` (the central forge's SSH host key lines) and `pin` (one `login key` line per admin
key, including backups). They become root-only files under `/etc/porelo-host/organization/`; repeated setup preserves
the pin advanced by a successful follow. Setup generates `read/organization` once as an Ed25519 key and returns its
public half as `organization_read_key` in `host.json`. `org pin` is unavailable. The directory and its `projects` and `persons`
subdirectories permit traversal so member ACLs work; credentials and applied state remain root-only.

Where the host has its Matrix gate installed, follow runs `keep-room --project <project> --persons <logins>` as
`porelo-matrix`, with only unlocked members, on every follow, and names who left the room in its journal. The project
file then names the gate as `homeserver` and the room `keep-room` answered; on a host with no gate both are null, and
Porelo decides at start whether a project's own homeserver goes first. A departing project's room first loses its
members, even if unpushed work holds the forge. Its conversation stays until forge removal succeeds, then the room is
dropped. Exit 75 is retried at the next follow; exit 78 is named in status and the room is left alone. No Matrix admins file is written.

Matrix admission stores no machine or registration token. Purge runs `porelo-message-transport-matrix expel <login>`
as `porelo-matrix`, including after a prior lock, with the homeserver administrator's token from
`porelo/matrix/gate/admin-token` in the `porelo-matrix` account's config folder on stdin alone. Every command run as another account
starts in `/` with that account's own `HOME`. See [Matrix access](../../doc/matrix.md) for the gate boundary.

The helper also provides `forge-token`, `task <task>`, `task --end <task>`, `task --show <fingerprint>` and root's
`sweep`. The person role installs their sudo rules and the daily persistent `porelo-host-task-sweep.timer`.
Certificates stay in root's private task records; token answers leave through stdout alone. See the
[task certificate contract](../../doc/task-certificates.md) for validation, Porelo's own check and token scopes.
`verify-push` answers the forge's pre-receive hook through its socket unit alone, and `arrivals <project>
<repository>`, through sudo for a person of the project, reads the verdicts in `/var/lib/porelo-host/arrivals`; see
[each push judged](../../doc/local-forge.md#each-push-judged-when-it-arrives).

The account-bound entry points (`main`, `project`, `down`) remain on disk for an explicit `porelo_account`
when called directly; `up` and `down` do not call them.

## Requirements

Ubuntu 26.04, run as root on the host itself (`-c local`).

## Variables

| Variable | Default | What it is |
|---|---|---|
| `porelo_distribution` | `{{ porelo_host_distribution \| default('releases') }}` | Which of Porelo's published distributions (`releases` or `snapshots`) the host installs from. |
| `porelo_key_url` | in `defaults/main.yml` | Where Porelo's package key is fetched from. |
| `porelo_key_fingerprint` | in `defaults/main.yml` | The fingerprint the package key must have. |
| `porelo_repository_url` | in `defaults/main.yml` | Porelo's apt repository. |
| `porelo_account` | required (account entry points only) | The account Porelo's tasks run as when an account entry point is called directly. |
| `porelo_machine_file` | `/etc/porelo-host/setup/machine.yml` | The machine file read by `project` and `down` when called directly. |

## Example

    - name: Install Porelo's packages and stop command
      hosts: localhost
      connection: local
      tasks:
        - name: Install Porelo
          ansible.builtin.include_role:
            name: porelo.host.porelo
            tasks_from: install

## Behaviour

**Idempotent**: a second run changes nothing, measured by Molecule's idempotence step. **Check mode**: the reading tasks
run in it too; a check run is not tested yet. **Rollback** is not offered; `down` stops the tasks and clears the vault,
and the packages stay with the host.

## License

GPL-3.0-or-later.

SSH policy and initial key/KRL installation belong to `base`. The person helper creates
`/run/porelo-host/people/<login>` (0700, owned by the person) with the link `porelod.sock` to the person's
`/run/user/<uid>/porelo/porelod.sock`, and a per-person tmpfiles rule for both at admission; lock and purge remove
them. Lock terminates sessions and stops the user manager even if a service hook refuses.
The follow applies card keys and expiries, rebuilds the KRL and locks revoked accounts, and applies each project's
person roles and locks to its forge teams and allowed signers. Other projects,
sessions and tokens stay until a host lock or last-membership removal. A project can restore a membership-only lock;
it cannot undo a host lock. `porelo-people` holds exactly unlocked admitted logins. Purge permanently records the login
in root's `0600` `/etc/porelo-host/people/purged` and refuses later admission.

Allowed signers live in `/etc/porelo-host/signers/<project>.allowed` (root-owned `0644`): each unlocked person has
a plain-key line and a task CA line restricted to namespace `git` and principals `task:*`. Rotation keeps the old key
with `valid-before` for history. Project signing keys remain verification anchors and are never commit signers.
See [person synchronization](../../doc/local-forge.md#keeping-a-projects-persons-in-step) and
[SSH access](../../doc/ssh.md). Device records are refused by the person helper.
