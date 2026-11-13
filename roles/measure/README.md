# measure

`files/porelo-host-measure` is one of the four collection script exceptions, using Python before Java is available.

Measure a fresh disposable local Ubuntu 26.04 machine as root, using Python's standard library and an installed
`porelo.host` collection with Ansible-core 2.19 or later. This role changes the machine: repeated `up` and `down`
leave packages, firewall settings and caches. It is not idempotent and refuses to replace a result file.
No tokens or vault setup are provided. An `up` needs an organization to follow: the run stands one in that does not exist, signed by a key whose
private half was thrown away when it was made, so its follow finds nothing. A `down` that fails leaves it, and the machine is then to be given back.
Like any `up`, a run needs root's own key in `/root/.ssh/authorized_keys`, exactly one `ssh-ed25519`, and closes root's login to it. Host hardening,
packages, the firewall and the JDK stay: the file's `changes` name packages, unit files, accounts and the directories at `/`, `/home` and `/var/lib`, and so not `/opt` or a file in `/etc`. **It is for a machine that is given back.**

The local playbook accepts these options:

| Option | Meaning |
| --- | --- |
| `measure_out` | Required absolute path for a new private JSON file on the machine; its parent must exist. |
| `measure_given` | Required `provider` and `offer` labels; no address, hostname, account or credential. |
| `measure_fresh` | Default `false`; the person's word that this machine is fresh and disposable. |
| `measure_distribution` | Default `releases`; `snapshots` for a collection newer than the last release, `up` then installing the newest `porelo` and `porelo-host` that channel's index names. It stands in the result. |
| `measure_packages` | Default empty; root's directory of handed-over packages as `build/stage-packages.sh` stages them. Every file is checked against its `SHA256SUMS` before anything changes, and `up` installs `porelo` and `porelo-host` from there at their `.version`; a `porelo-agent-stub` there is the stub. The digest of the sums stands in the result. In `build/molecule.sh measure` it is `PORELO_HOST_MEASURE_LOCAL=on`, with `PORELO_HOST_MEASURE_STEPS` and `PORELO_HOST_MEASURE_RAISE=on`. |
| `measure_steps` | Default `[idle]`; `task` measures stub tasks and `job` a Maven build in forge jobs, as below; `agent` is a placeholder with null and a reason. |
| `measure_tasks` | Default `2`, from 1 to 12; how many stub tasks the `task` step starts in each sample. |
| `measure_raise` | Default `false`; with `task`, also raise developers on one more `up`, as below. |

Example: in a root terminal on the disposable machine, with Ansible and the collection already installed:

```sh
ansible-playbook -c local porelo.host.measure -e @measure.json
```

The input file contains, for example:

```json
{"measure_out":"/tmp/measure.json","measure_given":{"provider":"local","offer":"small"},"measure_fresh":true}
```

The script can also be run from the installed collection's `roles/measure/files/` directory as root:

```sh
./porelo-host-measure --fresh --out /tmp/measure.json --given '{"provider":"local","offer":"small"}' --steps idle
```

It writes one versioned JSON object with a `facts` array. Every fact has an allowed
`field`, `value`, `unit` and `step`; observations also name their `sample` and resource `subject`.
A null always has `why`. All numbers use bytes, seconds or count. Three independent up/down cycles per shape
keep all three readings. `agent` remains absent even when requested.

The `job` step brings the host up in the forge's shape alone, once for each count: 1, 2 and 4 parallel jobs, and 4
past the half of the host with `porelo_host_work_share` at 90 on that `up` only. A count the forge's capacity check
refuses is null with that refusal. On each, the forge's admin carries `porelo-buildtools` onto the forge, branches it
at the pinned tag `v0.5.1` and checks that the tag is the commit it names, then commits a workflow that builds it with
Maven in that many parallel jobs on `ubuntu-24.04`. It runs once cold and once with the count's own cache. Each run
keeps its wall time from the commit to the last of its jobs' end, and the CPU the runner account took; the account's
memory peak is kept for the cold run alone, since a slice's peak cannot be set back between runs.
A failed or unanswered build, past 40 minutes, is null with its reason; a failed one's reason ends with the last two
lines of its first failed job's own log, read from the forge's volume before the repository goes, without times or
colours. The repository goes after each count, and
the host goes down.

The `task` step brings the host up in the room's shape, as the idle run does. In each of its three samples it then makes
one throwaway developer, `porelo-measure`, as a person's account is made: an account in `porelo-people`, kept by
linger. The developer gets a vault whose passphrase is made for the run and goes on standard input only, and a
committed checkout. Porelo's stub agent is in no package channel. The run fetches the one of the installed Porelo's
version from `porelo-dist-test/porelo-agent-stub/<version>/` and checks it against the SHA-256 beside it. The
developer puts it into its own home and names it in its `agents.d`; a stub that cannot be had or does not match is
null with its reason. Porelo starts no agent that is not signed in, so the developer signs the stub in with `porelo
vault login stub` at a terminal `script` gives it; the stub's login writes a fixture, with no account, network or
secret. It then starts `measure_tasks` stub tasks in `default` with
`--no-input --yes --detach`. Each start's time is kept; a start that fails is null with its reason, which ends with
the last two lines Porelo said, without colours. The developer's slice gives memory in use, its peak and the
anonymous part, and the CPU the starts took; `/home` gives the disk they grew. With no project naming the host's
gate, a developer's conversation is on a homeserver of its own, the user unit `porelo-matrix-homeserver.service`,
where a real host has one gate: its memory is kept as its own reading and the unit is stopped before the developer's
slice is read, here and in the raising. Afterwards the tasks and the account,
with the stub in its home, are taken away, each sample's whatever got made, and a developer that cannot be removed
ends the run like a failed down. A stub does no work, so `work.time` is null with that reason. A refused step is null with its
reason, and the later samples are not tried again.

With `measure_raise` (`--raise`), the `task` step then brings the host up once more and raises developers 1, 2, 4 and
on to 32, `porelo-measure-1` and on, each made as above with five stub tasks. After each level it waits for memory
to settle and reads the kernel's pressure twice, half a minute apart. It stops at the first start that fails, or when
the memory's pressure stays at 10% or more or the CPU's at 80% or more. The number of developers of the last level that
held is kept as `developers`, and `work` says what stopped it; where no level held, or the kernel tells no pressure,
`developers` is null with that reason. Every developer goes again, each tried even when one stays, and the host goes
down; a developer left behind then ends the run as a failed down does. `--raise` without `task` is refused.
Provider and offer are the person's short class labels. Collection version comes from its `MANIFEST.json` or
`galaxy.yml`; installed versions come from dpkg's database before and after the run.

The script refuses without changing files unless given `--fresh` and root, and refuses any person record under
`/etc/porelo-host/people` or `/var/lib/porelo-host/people`, and any `/etc/porelo-host`, `/var/lib/porelo-host` or forge account, as a `down` would
remove what they hold. Existing homeserver data is conservatively refused by its
service account or gate directory; the script cannot prove that a homeserver database contains no room.
It never writes person records. Its hosts are in the host's [test mode](../../doc/task-certificates.md#test-mode)
with `start-uncertified`, since no person on them could certify a task: each `up` says `TEST MODE` and each `down`
takes it away, and the developers' stub tasks start with `--yes`, uncertified. A machine-wide lock refuses concurrent runs or leftovers, and stays after a failed `down`
until the machine has been inspected and its leftovers removed. The result's directory is checked before any cycle starts, and the file appears only at the end.
The generated inventory
is private, contains only fixed local settings and the selected forge and room booleans, and is removed on exit.
`porelo_host_room` defaults to true in normal `up`; the measuring inventory turns it off for shapes without a room. That shape is the run's: a host
with people needs its room. Only an idle host is read: nothing here takes a run past the capacity check, so a shape the check refuses says so.

Each reading pauses for five seconds, then requires three consecutive observations of the top slices' and the host's memory, in use and with cache, within one percent or
one MiB of one another, whichever is larger, checking every two seconds for at most 24 seconds.
Unsettled readings are null. Cgroup v2 current and lifetime peak values cover the top slices and the service accounts' slices, by name; `host` is the
slices' sum. Missing peaks are null. A person's own slice is never read.
`statvfs` reports filesystem usage for `/`, `/var/lib`, `/var/cache`, `/home`, `/var/lib/containers` and
`/var/lib/porelo-host`; these overlap on a shared filesystem. They are not directory sizes.
`memory.current` holds the page cache; `memory.anon`, from `memory.stat`, is what is in use. The run lists installed packages, unit files, system
and service accounts and direct children of `/`, `/home` and `/var/lib` before
and after, and writes added and removed names. An account with a person's uid is not named at all. The result has mode `0600` and is published without replacement.

The role uses `command` on the installed collection's local script with `async: 14400`, `poll: 15`.
Unlike `script`, `command` supports async and keeps the collection metadata available beside the script.
Each up is bounded to ten minutes and each down to five, plus bounded settling. Actual duration is not measured;
a first run may take hours. Check mode skips measurement. A failed up records its known stop task, leaves remaining
readings of that shape null, and runs down before the next shape; a failed down stops without publishing a partial result.
A signal in an up, whether SIGINT, SIGTERM or SIGHUP, kills it with its process group and is followed by a down. In a down, it lets that down
finish and then stops, and a second one changes nothing. A down still bounded to five minutes can be killed at that bound, and the lock then stays.
The playbook only polls: interrupting it leaves the script running, so send the script SIGTERM to stop a run.
Exit 0 means the complete file was written, including nulls; 1 is a refusal; 2 means the run could not complete.

To make tables, review and copy the result into `doc/measures/` in the checkout and run
`python3 build/measure-tables.py`. The [machine page](../../doc/machines.md) keeps absent readings explicit.
