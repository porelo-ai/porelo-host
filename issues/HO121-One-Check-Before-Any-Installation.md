# HO121 — One Check Before Any Installation

**Status:** Idea.

**What must be true.** Before anything changes on a machine, one read-only check answers whether it can do what this person
wants, and names **every** finding at once: what was found, what was asked, what to do. `up` installs nothing unless it passes,
and it runs the same code, so the two cannot differ.

## Why

The stops are spread over 18 role files and run where they are used: some after packages, ssh and the firewall have changed,
and each ends the run at the first thing it finds. A person who rents a machine learns of a second lack only after fixing the
first, on a machine already changed. No stop looks at the disk.

## It cannot be a playbook

**Ansible is itself the first change:** the interface installs `ansible-core` on the host, by `apt-get`, before any playbook can
run. So the check is one Python script using only the standard library, `roles/check/files/porelo-host-check`, sent by ssh on
standard input from the tarball whose digest the interface has already checked. It writes no file. The person's choices come
in as JSON: KVM, Forgejo, its jobs, the pool, the store.

- **The interface runs it before `apt-get`,** in `host up` as well as in the window, or a run from the command line still changes
  the machine first. That is the interface's part.
- **`up`'s first task runs the same script,** so a playbook run without the interface stops the same way, though by then
  `ansible-core` is there.
- **It runs over the ssh connection pinned to the host key the person confirmed,** so the first thing it shows is that this key
  is the machine's. A key taken while a provider was still installing the server, seen on Elastic Metal, ends here, before any
  change, with the interface's words. The check does not fetch or trust a key itself.
- **A machine with no `python3`** can't run it. A person's image without it is the one finding that comes from the interface's
  own first ssh line, with login and `sudo -n`. So is root still being closed: no script runs behind that `command=` line, so the
  interface tells it by the login's exit and standard output, and `doc/lines.md` names it.

## What it reads

| Finding | Asked | Today |
| --- | --- | --- |
| Login, `sudo -n` | root, or sudo with no password | at the first step that fails |
| Root still closed: a cloud image's `command=` line in `/root/.ssh/authorized_keys`, which accepts the key, prints "Please login as the user", sleeps and exits non-zero; seen on Elastic Metal as an empty reason after 11 s | no such line, the login's exit 0 | the interface's first ssh, with no reason |
| The system finished installing: `cloud-init status`, no package lock | finished | the interface waits by `cloud-init status --wait` |
| System and version | Ubuntu 26.04 | `base`, no file found |
| CPUs, memory | [HO118](README.md#ho118)'s and the jobs' and pool's budget | `forge`'s `capacity`, `vm_pool`'s `memory` |
| Free disk, under the paths that grow | a limit once measured | no check |
| `vmx` or `svm`, with `porelo_host_kvm` | flag present | `base`'s `cpu` |
| cgroup v2, controllers `cpu`, `memory`, `pids`, what systemd delegates to a user | present | `base`'s `controllers`, late, per account |
| IPv4 default route, address on it, ed25519 host key | present | `base`'s `firewall` and `host`, late |
| Ports the host's choices need, on loopback | free | no check |
| What `apt`, the package repository and images need, by name | answers | at the step that fails |
| The inventory's values: name, network, pool's shape, job bounds | valid | `up`, `vm_pool`, `forge` |

Each finding moves here from its role, and the late stop stays only where a state can change between the check and the task,
or where the check cannot see it. A table of all 18 files, stop by stop, moved or kept and why, goes in this issue as the first
step of building.

**One source for the budget.** `forge`'s `capacity` chooses the jobs and refuses them, in Jinja, and the check must give the same
answer. So the script holds the formula and `capacity` calls it; its unit tests go on holding the same numbers.

**Limits** stand in one file, read by the script. Until [HO119](README.md#ho119) has numbers they are today's; the disk has none
yet, so it is reported, with its measured value, and refuses nothing.

## The answer

One JSON object on standard output, its version in it, `ok`, `complete` for whether the check ran to its end, and every finding: a
stable `id`, `pass`, `fail`, `warn` or `unknown`, the value and unit found, what was asked, what to do in words the window can
show. `unknown` is what could not be known beforehand, and no one reads it as passed. Exit 0 when nothing fails, 1 when something
does, any other when the check itself could not run. It reads no secret and answers none. `doc/lines.md` says it, for the
interface.

## What cannot be known beforehand

- **That KVM really works.** A flag says the CPU offers it; a firmware may have it off, and `/dev/kvm` may not exist until a
  package loads the module, and loading it is a change. So `up` still asks KVM after installing.
- **That the account's controllers arrive.** The account does not exist yet; systemd's default is read, the real account after setup.
- **The store's bucket**, on a host with one: the keys come at the person's step, by design.
- **That the packages install,** or that an image pulls: a name that answers can still fail.
- **Reach from outside,** which the host cannot see of itself: only ssh, by having got in.
- **How it will run under load:** that is what [HO120](README.md#ho120) measures.

## Order

[HO118](README.md#ho118) first: small, and the setting this check reads. Then this, with today's limits. Then
[HO120](README.md#ho120), then [HO119](README.md#ho119), whose numbers go in the limits file.

## Acceptance

- Unit, the script against a directory of fixture files standing in for `/proc`, `/sys` and `/etc`: all findings together on a
  machine lacking several, each value and asked as named, exit codes as said, no finding for a choice not made.
- Molecule, on a VM with too little memory for the jobs asked, KVM asked with `vmx` and `svm` off, and a port taken: the check
  lists all three; `up` stops at its first task; `dpkg -l` and a listing of `/etc` and `/var/lib` are the same before and after.
- Molecule, a machine that passes: the check writes nothing, and `up` goes on as today.
- A unit test holds the script's budget against `capacity`'s known numbers.
- The table of stops is in this issue, and each stop moved is gone from its role.
