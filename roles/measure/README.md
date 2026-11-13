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
| `measure_distribution` | Default `releases`; `snapshots` for a collection newer than the last release. It stands in the result. |
| `measure_steps` | Default `[idle]`; `task` measures stub tasks, as below; `agent` and `job` are placeholders with null and a reason. |
| `measure_tasks` | Default `2`, from 1 to 12; how many stub tasks the `task` step starts in each sample. |

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
keep all three readings. `agent` and `job` remain absent even when requested.

The `task` step brings the host up in the room's shape, as the idle run does. In each of its three samples it then makes
one throwaway developer, `porelo-measure`, as a person's account is made: an account in `porelo-people`, kept by
linger. The developer gets a vault whose passphrase is made for the run and goes on standard input only, and a
committed checkout. It installs `porelo-agent-stub` and starts `measure_tasks` stub tasks in `default` with
`--no-input --detach`. Each start's time is kept. The developer's slice gives memory in use, its peak and the
anonymous part, and the CPU the starts took; `/home` gives the disk they grew. Afterwards the tasks, the account and
the stub package are taken away, each sample's whatever got made, and a developer that cannot be removed ends the run
like a failed down. A stub does no work, so `work.time` is null with that reason. A refused step is null with its
reason, and the later samples are not tried again.
Provider and offer are the person's short class labels. Collection version comes from its `MANIFEST.json` or
`galaxy.yml`; installed versions come from dpkg's database before and after the run.

The script refuses without changing files unless given `--fresh` and root, and refuses any person record under
`/etc/porelo-host/people` or `/var/lib/porelo-host/people`, and any `/etc/porelo-host`, `/var/lib/porelo-host` or forge account, as a `down` would
remove what they hold. Existing homeserver data is conservatively refused by its
service account or gate directory; the script cannot prove that a homeserver database contains no room.
It never writes person records. A machine-wide lock refuses concurrent runs or leftovers, and stays after a failed `down`
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
