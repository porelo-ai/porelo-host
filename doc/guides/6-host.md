# Sprints 6j to 6l: the host's side of the pass

The host's checks in the operator's one pass over sprints 6j, 6k and 6l. The pass covers:

- a host prepared with its forge;
- the project admin admitted and the project registered;
- the project brought from GitHub in the admin's own account and joined in the developer's;
- both people pushing through the host;
- the developer's laptops and the developer kept to the signed access file;
- the project taken off and the people locked and purged.

Agent Frontend's walk 23 does each act in the interface, on laptop A, walkadmin's VM or laptop B, and then sends you to
the step of the same name here. After its check, go back to the walk. Agent Core's checks
(`~/.porelo/handover/porelo/6-pass/`) and Agent Matrix's (`~/.porelo/handover/porelo-message-matrix/6-pass/`) hang on
these steps too. Each step below says which of theirs follows it.

**Versions:**

- porelo-host built from commit `2443282`. On laptop A the tarball is
  `~/.porelo/handover/porelo-host/2443282/porelo-host-0.5.9-snapshot.tar.gz`, sha256
  `005fcd24363aebcac123e6d50df5dc8510461d7a2576ea240baac3d0ac32913e`. The walk's first step names it.
- The packages on the host are those the walk names.

**Seen to work:**

- Every host-side behavior these checks read ran on a test VM in the collection's Molecule scenario on 2026-10-30
  (run `20261030t050056z-3899440` on `363f921`, green; `2443282` adds only issue states and `AGENTS.md`), with the
  names `alpha`, `bo`, `cy` and `alpha-one` in place of the pass's.
- The scripts were rehearsed against a stand-in host. It was a container laid out as each act leaves the host,
  reached through a stand-in `ssh`. A real HTTPS server signed by a stand-in CA answered the forge's API, and stand-ins
  answered for `wg`, `sshd`, `podman`, `systemctl --user`, `porelo` and GitHub. Each script passed on the state its
  act leaves and failed, naming the step, on the state before. It also failed on:
  - a second repository whose main differs from GitHub's;
  - a missing team;
  - a missing project record;
  - a missing account.
- They have not run against a rented host.

**Not run:**

- The steps changed on 2026-10-30 for the walk's new order were not rehearsed against the stand-in host:
  host-bring.4 and .5, host-join.4 and host-sync two's step 2, and the new host-push-run.
- The developer's VPN on laptop B: laptop B's interface brings it up; this guide checks only the host's peer.
- `down` after the pass: nothing below checks it.

**About 20 minutes** for the host's checks, beside the walk.

## Before you start

- Laptop A is your own computer, where you are host admin. The project admin `walkadmin` works from a VM of its own,
  its laptop `walklaptop`, as michi decided: one laptop holds one VPN identity per host. Laptop B is the account
  `walkdev` on test-ubuntu-vm, the developer `walkdev`. Walk 23 says how to prepare walkadmin's VM and laptop B.
- Every command below runs **on laptop A, in your own account, in Claude with `!`**. The scripts ask for nothing.
  They lie in `~/.porelo/handover/porelo-host/6/` on laptop A.
- They take the host from the interface's settings on laptop A (`~/.config/porelo/frontend.json`, `hostUps.walk6`):
  - its network `<n>`;
  - the private key you named in the wizard;
  - the host key the host reported.

  They log in as `root@10.73.<n>.1` over the VPN, as the interface's helpers do, and accept only that host key. They
  read the host's forge with the forge's own token, which never leaves the host.
- Each script only reads, so it can run twice. Where something it needs is missing, it stops with exit 69 before
  anything is sent to the host, saying what is missing.
- A check that fails prints `expected:` and `got:`, then `<step> failed`, and exits 1. Note the step and go on with
  the walk; the findings are discussed together at the end.
- Other names than walk6, walkadmin, walkdev, walklaptop and walk6-demo are given as `PORELO_GUIDE_HOST`, `_PERSON`,
  `_DEVELOPER`, `_LAPTOP` and `_PROJECT`.

<a id="laptop-prepare"></a>

## laptop-prepare: laptop A ready

Before the walk's first step, before any host is rented.

**laptop-prepare 1.** Run:

    ! bash ~/.porelo/handover/porelo-host/6/6-host-laptop-prepare.sh

Expected:

- **laptop-prepare.1** `ok: jq ssh git sha256sum python3`: the tools the checks call. If one is missing, the script
  names the `sudo apt install` line for it.
- **laptop-prepare.2** `ok: <k> files`: every file of this hand-over matches its `SHA256SUMS`.
- **laptop-prepare.3** `ok: <k> files`: so does every file of Agent Matrix's hand-over.
- **laptop-prepare.4** `ok: github.com/porelo-ai/walk6-demo`: laptop A reads the project's GitHub repository with its
  own git credentials, as host-push will.
- **laptop-prepare.5** `ok: porelo-host-0.5.9-snapshot.tar.gz`: the collection's tarball is the one built from
  `2443282`, the one the walk installs.

Then `laptop-prepare passed`. Nothing is changed.

<a id="host-prepare"></a>

## host-prepare: the host prepared with its forge

After the walk's step that brings the VPN up on laptop A.

**host-prepare 1.** Run:

    ! bash ~/.porelo/handover/porelo-host/6/6-host-prepare.sh

Expected, each line with `ok:`:

- **host-prepare.1** the summary in `/etc/porelo-host/host.json` is identical to the one the interface recorded;
- **host-prepare.2** `ok: 0|0`: no person admitted, no project registered;
- **host-prepare.3** `ok: 200`: the homeserver answers at `https://matrix.walk6.porelo.internal:8448`, trusted by your
  CA;
- **host-prepare.4** `ok: 200`: the forge answers at `https://forge.walk6.porelo.internal:3000`, trusted by your CA;
- **host-prepare.5** `ok: ` with nothing after it: the forge has no user named `operator`, each person's login is
  their own;
- **host-prepare.6** `ok: present|present|1`: `porelo-host-person` with its `sync`, `porelo-host-push`, and the rule
  that lets a project's admin run `sync` with sudo.

Then `host-prepare passed`. On a host prepared without a forge, it stops with exit 69 before step 1.

Then Agent Matrix's **matrix-prepare**.

<a id="host-person-admit"></a>

## host-person-admit: the project admin admitted

After the walk's step that admits you as the project admin.

**host-person-admit 1.** Run:

    ! bash ~/.porelo/handover/porelo-host/6/6-host-person-admit.sh

Expected:

- **host-person-admit.1** `ok: member=hand|locked=false|laptop=walklaptop 10.73.<n>.3`: walkadmin's VM has the next
  free address after the host's;
- **host-person-admit.2** `ok: from="10.73.<n>.3" ssh-ed25519`: ssh lets walkadmin's key in from that address alone;
- **host-person-admit.3** `ok: ok`: `sshd -t` accepts the configuration with your drop-in;
- **host-person-admit.4** `ok: 10.73.<n>.3/32`: the VPN has walkadmin's VM as a peer;
- **host-person-admit.5** `ok: walkadmin 600`: the homeserver's registration token waits in your home, yours alone;
- **host-person-admit.6** `ok: walkadmin 600`: the forge identities' tokens wait in
  `/run/porelo-host/people/walkadmin/`, yours alone.

Then `host-person-admit passed`. No token is printed.

Then Agent Matrix's **matrix-person-admit** for `walkadmin`.

<a id="host-project-register"></a>

## host-project-register: the project registered

After the walk's step that registers walk6-demo with its signing key.

**host-project-register 1.** Run:

    ! bash ~/.porelo/handover/porelo-host/6/6-host-project-register.sh

Expected:

- **host-project-register.1** `ok: admin=walkadmin|signed_by=…|publisher=porelo-publisher-walk6-demo`: the project's
  record, with no bring yet;
- **host-project-register.2** `ok: member=hand|member=walk6-demo project-admin|locked=false|laptop=walklaptop …`: your
  record gains the project's admin membership after hand;
- **host-project-register.3** `ok: walk6-demo|0`: the forge holds the project's organization, still without a
  repository;
- **host-project-register.4** `ok: porelo-publisher-walk6-demo`: the forge holds the project's publisher.

Then `host-project-register passed`.

<a id="host-bring"></a>

## host-bring: the project brought in your own account

After the walk's step that brings walk6-demo onto the host from walkadmin's VM. The interface writes your setup files
into your account on the host. It then runs `ansible-playbook -c local porelo.host.bring -e porelo_project=walk6-demo`
there as you, with no sudo. The bring:

- migrates the project's repositories from GitHub into the host's forge;
- writes your push config;
- follows the project in your Porelo;
- runs `sync` against the signed access file, which lists no developer yet: the walk adds walkdev after the bring;
- starts your sync timer;
- makes the project's room with `porelo talk room walk6-demo` in your account.

  For that, walk6-demo's `project.yml` must name a peer whose address is `matrix:` under `mail.peers`, such as
  `people: {address: "matrix:", trust: external}`. Without one the bring stops at that task with "'walk6-demo' has no
  conversation". The signed `access.yml` must also name the host's homeserver and the room:
  `transports: {matrix: {homeserver: "https://matrix.walk6.porelo.internal:8448", room:
  "#porelo-walk6-demo:matrix.walk6.porelo.internal", registration_token_file:
  "~/.config/porelo/matrix/host-registration-token", ca_certificate: "<your CA's certificate as PEM text>"}}`.
  The token file is where admission leaves each person's token. The CA is the one that signed the homeserver's
  certificate. Without it the bring stops with "the access file of
  walk6-demo names no settings for the matrix transport".

**host-bring 1.** Run:

    ! bash ~/.porelo/handover/porelo-host/6/6-host-bring.sh

Expected:

- **host-bring.1** `ok: admin=walkadmin|…|commit=<40 hex>|access_commit=<40 hex>|signer=…`: the project's record
  holds the commits the bring verified and their signer;
- **host-bring.2** `ok: walkadmin 700|walkadmin 600|walkadmin 600|walkadmin 600`: your setup directory and its
  `machine.yml`, `project.bundle` and `access.bundle` are yours alone;
- **host-bring.3** `ok: walk6-demo https://github.com/porelo-ai/walk6-demo true false fast-forward-only`, one entry
  per repository: each was migrated from GitHub, private, no mirror, main fast-forward only;
- **host-bring.4** `ok: developers=|gates=|agents=`: the teams are there, and nobody is in any of them yet;
- **host-bring.5** `ok: absent`: walkdev is not on the host yet. The walk adds them after the bring, and host-sync two
  checks them;
- **host-bring.6** `ok: walkadmin 600|local https://10.73.<n>.1:3000|owner walk6-demo|central-ca …|repository
  walk6-demo https://github.com/…`: your push config;
- **host-bring.7** `ok: enabled|active`: your sync timer runs in your own account;
- **host-bring.8** `ok: true`: your Porelo follows the project, verified;
- **host-bring.9** `ok: absent|absent`: no forge token is left in your runtime directory.

Then `host-bring passed: <repositories>`.

Then:

- Agent Core's **B314-1** to **B314-3** (`porelo-checks-room.sh`): the room the bring made; <!-- not-a-citation: Agent Core's step names -->
- Agent Matrix's **matrix-room 1**.

<a id="host-join"></a>

## host-join: the developer joined in their own account

After the walk's step on laptop B that joins walk6-demo, which comes after host-sync two. Laptop B's interface uploads
walkdev's setup files and runs `porelo.host.join` as walkdev, with no sudo.

**host-join 1.** Run, on laptop A:

    ! bash ~/.porelo/handover/porelo-host/6/6-host-join.sh

Expected:

- **host-join.1** `ok: walkdev 700|walkdev 600|walkdev 600|walkdev 600|0`: walkdev's setup files are walkdev's alone,
  and the `machine.yml` names no forge section;
- **host-join.2** `ok: walkdev 600|same`: walkdev's push config names the same forge, organization and repositories
  as yours;
- **host-join.3** `ok: true`: walkdev's Porelo follows the project, verified;
- **host-join.4** `ok: member=walk6-demo developer|locked=false|laptop=l1 …|laptop=l2 …`: the join changed no
  membership;
- **host-join.5** `ok: absent|absent`: no forge token is left in walkdev's runtime directory.

Then `host-join passed`.

Then:

- Agent Core's **B331-1**, **B331-2**, **B310-1**, **B310-2** and **B311-1** to **B311-3**, after the join: walkdev's <!-- not-a-citation: Agent Core's step names -->
  Porelo follows from the access bundle in walkdev's setup directory, made by the join, not by the sync;
- Agent Matrix's **matrix-room 2**, once walkdev's Porelo has set up its messages.

<a id="host-push"></a>

## host-push: both pushes reached GitHub

After the walk's steps where a change reached main on the host's forge, through a pull request merged there. Each
push is the gathered push, `porelo-host-push walk6-demo`, in the person's own account on the host.

**host-push-run.** This one is an act, not a check: it pushes to GitHub. Run it once for each person, on laptop A:

    ! bash ~/.porelo/handover/porelo-host/6/6-host-push-run.sh walkadmin
    ! bash ~/.porelo/handover/porelo-host/6/6-host-push-run.sh walkdev

It takes the GitHub token from laptop A's own git credentials and hands it to the host only on ssh's standard input.
For walkdev, too, that is laptop A's token. Expected, each time:

- **host-push-run.1** `ok: …member=walk6-demo …|locked=false…` and `ok: present`: the person is on the host, unlocked,
  with a push config;
- **host-push-run.2** `ok: a token is there (not shown)`;
- **host-push-run.3** porelo-host-push's own lines, then `ok: pushed`.

Then `host-push-run passed`. Not run yet: the script has run against neither a host nor a stand-in.

**host-push 1.** Run:

    ! bash ~/.porelo/handover/porelo-host/6/6-host-push.sh

Expected:

- **host-push.1** one step for each repository, `ok: <40 hex>`: main on the host's forge is the main laptop A reads
  from GitHub;
- **host-push.2**, or the step after the last repository, `ok: absent|absent`: no central token is left in yours or
  walkdev's runtime directory.

Then `host-push passed`.

<a id="host-sync"></a>

## host-sync: the host kept to the signed access file

The walk changes the access file three times. Each time, you sign a new commit of it on walkadmin's VM, and the
interface uploads the bundles to your setup directory. Your sync timer runs `sync` within a minute, or the interface
runs it at once. Run the check after each change, with one argument: what the file now lists for walkdev.

**host-sync two:** after the walk adds walkdev with two laptops, l1 and l2. Run:

    ! bash ~/.porelo/handover/porelo-host/6/6-host-sync.sh two

Expected:

- **host-sync.1** `ok: access_commit=<40 hex>`: the project's record took the newest commit;
- **host-sync.2** `ok: member=walk6-demo developer|locked=false|laptop=l1 …|laptop=l2 …`: walkdev is admitted with
  both laptops, each at the address the file gave it;
- **host-sync.3** `ok: from="…"|from="…"`: ssh lets in exactly those two laptops, each from its own address;
- **host-sync.4** `ok: 10.73.<n>.<b>/32|10.73.<n>.<c>/32`: the VPN has both as peers;
- **host-sync.5** `ok: walkdev`: walkdev is in the developers team.

Then `host-sync two passed`.

Then:

- Agent Core's **B314-1** to **B314-3** again: the room after the sync that admitted walkdev; <!-- not-a-citation: Agent Core's step names -->
- Agent Matrix's **matrix-person-admit** for `walkdev`, since this sync admitted the developer;
- then the walk's join, and host-join.

**host-sync one:** after the walk drops the second laptop. Run:

    ! bash ~/.porelo/handover/porelo-host/6/6-host-sync.sh one

Expected: as for two, with l1 alone in steps 2 to 4. Then `host-sync one passed`.

**host-sync none:** after the walk drops walkdev from the access file. Run:

    ! bash ~/.porelo/handover/porelo-host/6/6-host-sync.sh none

Expected:

- **host-sync.2** `ok: locked=true…`: walkdev has no membership left, so the host locked them;
- **host-sync.3** `ok: absent`: no ssh key of walkdev is left;
- **host-sync.4** `ok: ` with nothing after it: no VPN peer of walkdev is left;
- **host-sync.5** `ok: ` with nothing after it: the developers team is empty;
- **host-sync.6** `ok: true|absent`: walkdev's forge logins are prohibited, and their homeserver token is gone.

Then `host-sync none passed`.

Then Agent Matrix's **matrix-room 3**, with its **matrix-person-lock** for `walkdev`.

<a id="host-project-remove"></a>

## host-project-remove: the project taken off

After the walk's step that takes walk6-demo off the host. `remove` first runs the gathered push's check for every
repository, reading each one's GitHub address from the forge. It refuses while a repository holds commits GitHub does
not have.

**host-project-remove 1.** Run:

    ! bash ~/.porelo/handover/porelo-host/6/6-host-project-remove.sh

Expected:

- **host-project-remove.1** `ok: absent`: the project's record is gone;
- **host-project-remove.2** `ok: |`: the forge holds neither the organization nor the publisher;
- **host-project-remove.3** `ok: member=hand|locked=false|laptop=walklaptop 10.73.<n>.3`: you keep hand alone.

Then `host-project-remove passed`.

<a id="host-person-lock"></a>

## host-person-lock: the project admin locked

After the walk's step that locks you.

**host-person-lock 1.** Run:

    ! bash ~/.porelo/handover/porelo-host/6/6-host-person-lock.sh

Expected:

- **host-person-lock.1** `ok: locked=true`;
- **host-person-lock.2** `ok: absent|`: no ssh key and no VPN peer of yours is left;
- **host-person-lock.3** `ok: absent`: the registration token is gone from your home;
- **host-person-lock.4** `ok: L|1`: the account's password is locked and the account expired on day 1;
- **host-person-lock.5** `ok: true`: your forge logins are prohibited.

Then `host-person-lock passed`.

Then Agent Matrix's **matrix-person-lock** for `walkadmin`.

<a id="host-person-purge"></a>

## host-person-purge: both people purged

After the walk's steps that purge you and walkdev.

**host-person-purge 1.** Run:

    ! bash ~/.porelo/handover/porelo-host/6/6-host-person-purge.sh
    ! bash ~/.porelo/handover/porelo-host/6/6-host-person-purge.sh walkdev

Expected for each:

- **host-person-purge.1** `ok: absent|absent|absent`: the account, its home and its record are gone;
- **host-person-purge.2** `ok: <person>|true`: the forge keeps the person's login, prohibited, so its name is never
  given to someone else.

Then `host-person-purge passed`.

Then Agent Matrix's **matrix-person-purge** for each.

## What the host does not do yet

- **`remove` leaves your push config and sync timer for the project in your account.** The timer's `sync` then
  refuses the unregistered project at each run, until purge deletes the account.
- **`down` leaves the people:** it takes away the host's services but not an admitted person's account, record, VPN
  peer file, ssh key file, sudoers rule and sshd drop-in. The walk purges both people before giving the server back.