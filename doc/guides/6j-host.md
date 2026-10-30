# Sprint 6j: the host's side of the walk

The host's checks in the operator's walk of sprint 6j: a host prepared with no project or person, a project admin
admitted, a project registered and removed, the admin locked and purged. Agent Frontend's walk of the sprint does
each act in the interface and then sends you to the step of the same name here; after its check, go back to the
walk.

**Versions:**

- porelo-host built from commit `b5209b1`: `~/.porelo/handover/porelo-host/b5209b1/porelo-host-0.5.9-snapshot.tar.gz`
  on the laptop, sha256 `2a5fa90c76be72e87c5436fe965cc35379fad61db4f8fd9acd49734882265db1`, which the walk's
  first step names;
- on the host, the homeserver packages `porelo-matrix-homeserver` and `porelo-message-transport-matrix`
  `0.5.1~snapshot.0+local.20261029T131907` (Agent Matrix's `49a567a`).

**Seen to work:** every check below ran on a test VM in the collection's Molecule scenario on 2026-10-29 (run 12,
green, with exactly these packages), with the names `alpha`, `ada` and `alpha-one` in place of the walk's. The scripts that run the checks here
were rehearsed against a stand-in host: a container laid out as each act leaves the host, its `wg`, `curl`, `sshd`
and `runuser` answering as the VM did, reached through a stand-in `ssh`. Each script passed on its state and failed,
naming the step, on the state before it. They have not run against a rented host.

**Not run:** that Porelo in the admin's account registers on the homeserver as `walk6j-walkadmin`. A person's Porelo
registers only when it first sets up a project's messages, after `project follow`, which comes with the bring
(the project brought in its admin's own account); a 6j host follows no project.

**About 10 minutes** for the six checks, beside the walk.

## Before you start

- The walk has rented the host `walk6j` and brought the VPN up on the laptop (its step 2-1).
- `jq` is installed on the laptop (`sudo apt install jq` if `jq --version` fails).
- Every command below runs **on the laptop, in your own account, in Claude with `!`**: the scripts ask for nothing.
  They lie in `~/.porelo/handover/porelo-host/6j/` on the laptop. They take the host from the interface's settings
  (`~/.config/porelo/frontend.json`, `hostUps.walk6j`): its network `<n>`, the private key you named in the wizard,
  and the host key the host reported. They log in as `root@10.73.<n>.1` over the VPN, as the interface's helpers do,
  and accept only that host key. Where the settings lack the host or its key, they stop before anything is sent
  (exit 69), saying why.
- A check that fails prints `expected:` and `got:`, then `<step> failed`, and exits 1. Note the step and go on with
  the walk; the findings are discussed together at the end.

<a id="host-prepare"></a>

## host-prepare: the host prepared alone

After the walk's step 2-1, which brings the VPN up.

**host-prepare 1.** Run:

    ! bash ~/.porelo/handover/porelo-host/6j/6j-host-prepare.sh

Expected, each line with `ok:`:

- host-prepare.1 the summary in `/etc/porelo-host/host.json`, the seven fields the interface recorded, identical;
- host-prepare.2 `ok: 0`: no person admitted;
- host-prepare.3 `ok: 200`: the homeserver answers at `https://matrix.walk6j.porelo.internal:8448` on
  `10.73.<n>.1`, trusted by your CA;
- host-prepare.4 `ok: 200`: the forge answers at `https://forge.walk6j.porelo.internal:3000`, where the host runs one;

then `host-prepare passed`.

<a id="host-person-admit"></a>

## host-person-admit: the project admin admitted

After the walk's step 3-3.

**host-person-admit 1.** Run:

    ! bash ~/.porelo/handover/porelo-host/6j/6j-host-person-admit.sh

Expected:

- `ok: locked=false|laptop=walklaptop 10.73.<n>.3`: the laptop has the next free address after yours;
- `ok: from="10.73.<n>.3" ssh-ed25519`: ssh lets that key in from that address alone;
- `ok: ok`: `sshd -t` accepts the configuration with the person's drop-in;
- `ok: 10.73.<n>.3/32`: the VPN has the laptop as a peer;
- `ok: walkadmin 600`: the homeserver's registration token waits in the admin's home, theirs alone;
- `ok: walkadmin 600`: the forge identities' tokens wait in `/run/porelo-host/people/walkadmin/`, where the host runs
  a forge;

then `host-person-admit passed`. No token is printed.

<a id="host-project-register"></a>

## host-project-register: the project registered

After the walk's step 4-3.

**host-project-register 1.** Run:

    ! bash ~/.porelo/handover/porelo-host/6j/6j-host-project-register.sh

Expected: `ok: admin=walkadmin|publisher=porelo-publisher-walk6j-demo`, then `ok: porelo-publisher-walk6j-demo` (the
forge holds the publisher), then `host-project-register passed`. On a host without a forge it stops with exit 69.

<a id="host-project-remove"></a>

## host-project-remove: the project taken off

After the walk's step 5-3. The project holds no repository, so its removal asks for no central forge token. A project
that held one would be refused in this sprint: comparing with the central forge comes with the bring.

**host-project-remove 1.** Run:

    ! bash ~/.porelo/handover/porelo-host/6j/6j-host-project-remove.sh

Expected: `ok: absent` (the project's record), then `ok: ` with nothing after it (no publisher left), then
`host-project-remove passed`.

<a id="host-person-lock"></a>

## host-person-lock: the project admin locked

After the walk's step 6-2.

**host-person-lock 1.** Run:

    ! bash ~/.porelo/handover/porelo-host/6j/6j-host-person-lock.sh

Expected:

- `ok: locked=true`;
- `ok: absent|`: no ssh key of the admin, and no VPN peer at `10.73.<n>.3`;
- `ok: absent`: the registration token is gone from the admin's home;
- `ok: L|1`: the account's password is locked and the account expired on day 1;

then `host-person-lock passed`.

<a id="host-person-purge"></a>

## host-person-purge: the project admin purged

After the walk's step 7-2. Purge clears the admin's vault in their own account first: it lifts only the account's
expiry for that, starts their user manager, stops their tasks, clears the vault, stops the manager and deletes the
account. If any of that fails, the account is expired again and kept, and purge can run again.

**host-person-purge 1.** Run:

    ! bash ~/.porelo/handover/porelo-host/6j/6j-host-person-purge.sh

Expected: `ok: absent|absent|absent` (the account, its home and its record), then `host-person-purge passed`.

## What the host does not do yet

- `down` takes the host's services away but not the people: an admitted person's account, record, VPN peer file,
  ssh key file, sudoers rule and sshd drop-in stay. The walk purges the admin before giving the server back, so
  nothing of them is left on this host.
