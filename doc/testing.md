# Testing the collection

The collection's roles are tested on a VM made for the run, never in a container and never on a machine another run
uses: a role installs packages, KVM and system services, and only a fresh machine shows what it did.

    PORELO_HOST_MOLECULE_POOL=off build/molecule.sh default

runs the Molecule scenario `extensions/molecule/default` against such a VM, through libvirt on the machine it is
started on (`qemu:///system`, pool `images`, network `default`). It needs libvirt, `qemu-img`, `virt-install`,
`xorriso`, ssh and podman there; Molecule itself runs from the image `build/tools-image` pins.
The development machine also needs `dpkg-deb` to inspect the local packages.

Export `PORELO_HOST_PACKAGES` as the absolute directory holding Porelo's local Debian packages and `PORELO_HOST_DEB`
as the path to the selected local `porelo-host` Debian package. The latter is required: a missing or unreadable value
stops before a VM is made. Identical duplicate artifacts are accepted once; different artifacts with the same package
identity are refused. Both program pins come from Debian metadata, independently of the collection version.
The staged package manifest selects a separate root-owned directory on the VM, and up installs from there.

The default scenario without pool acceptance is:

    PORELO_HOST_MOLECULE_POOL=off build/molecule.sh default

For the pool scenario, also export `PORELO_HOST_MACHINES` as the checked runtime JAR directory and
`PORELO_HOST_MACHINES_SHA256` as its independently supplied `SHA256SUMS` digest, then run:

    PORELO_HOST_MOLECULE_POOL=on build/molecule.sh default

The pool run needs KVM and the forge enabled. Package version and legacy-program absence verification are active.
Organization follow and pool/gate acceptance use the package. The organization CLI fixture temporarily diverts the
installed CLI at its checked system path, then restores it even if the follow act fails. Manual purge and desktop
interaction checks remain skipped because the package supplies no corresponding commands. A local run takes the
package from `PORELO_HOST_DEB`, a hand-over or `build/fetch-host-deb.sh`; GitHub's runner fetches the pinned one.

**What a run makes and leaves.** One domain and two volumes, its disk and its cloud-init seed, all named
`porelo-host-molecule-<run>`. It deletes them at its end, after a failure and on an interrupt too, and believes that
only once libvirt lists none of them; otherwise it names what it left and exits 1. It refuses to start while anything
of that name is still there. What it keeps is a cache, named by its digest: the Ubuntu 26.04 cloud image in
the build's cache folder in the developer's home, and its base volume `porelo-host-base-<digest>.qcow2` in the pool.

`PORELO_HOST_MOLECULE_KEEP=on` keeps the VM and its files when the run fails, so the failing scenario can be run again
on it; a later run refuses until that VM is deleted.
`PORELO_HOST_MOLECULE_KVM=off` runs the scenario as a host that asks for no KVM, on a VM whose CPU has `vmx` and `svm` disabled, and
needs `PORELO_HOST_MOLECULE_POOL=off`.

`PORELO_HOST_MOLECULE_TRANSPORT` names a transport executable inside the checkout, as the run sees it, to install in
place of the published one.

`PORELO_HOST_IMAGES` names an absolute directory of the forge's pinned images as OCI archives, each named
`<digest>.tar` by the image's sha256 digest; it may hold nothing else. The run copies them into the VM, and `up` loads
each one through the forge role's `forge_image_archives` instead of pulling it from its registry. Unset, every image is
pulled.

**The VM** is Ubuntu 26.04 from the cloud image `build/test-image` pins by URL and SHA-256, 4 vCPUs and 4 GB, with the
host's CPU passed through so KVM runs inside it, as on a rented host. Its ssh host key is made for the run and is the
only one accepted.

**What the scenario does** is what `host up` does on a host: Ubuntu's own `ansible-core`, the collection installed from
its tarball, and `porelo.host.up` run on the machine itself with `-c local`. A second converge must change nothing,
and `verify` reads on the machine what `up` promises. Local packages arrive before the first up. The run's machine
file is uploaded into the host's setup directory as the interface does; no removed stop wrapper is invoked.

**In the Build** the same script runs on GitHub's runner, after the linters and the tarball, on `main` and on the
project's own pull requests: about three minutes, the runner adding libvirt by pinned versions first.

**The forge's images in the Build** come from a cache, so the `molecule` job stays green while codeberg.org,
code.forgejo.org or docker.io does not answer. A step reads the three pinned references from
`roles/forge/vars/main.yml`. `actions/cache` restores `$RUNNER_TEMP/images` under the key `forge-images-` and the hash
of their digests. An image the cache lacks is fetched once with `skopeo copy --all --preserve-digests` as an OCI
archive, whose index keeps the pinned digest, and the cache is saved right after, before the scenario runs. Each
archive's digest is checked against its pin before Molecule gets it as `PORELO_HOST_IMAGES`.

Only the newest pins stay cached. A new pin makes a new key, so an old key is never restored again. GitHub removes a
cache entry that no run used for 7 days, so an old digest's entry ages out by itself. No step deletes entries.

**How long it takes**, measured on this project's workstation (16 threads, AMD): about a minute from start to clean-up
with the image cached - 52 s for a run whose `up` has no role yet, of which the VM takes about 15 s to answer ssh.
The first run on a machine also downloads the image, 825 MB, about 70 s at the measured 12 MB/s.

## Rehearsing a move

An agent's move can be rehearsed before a host is rented, on a VM made the same way on the development machine:

    build/rehearse-move.sh start [--machine-file <file> | --bare] [--cpus <n>] [--memory <GiB>] [--disk <GiB>]
    build/rehearse-move.sh ssh [<command>...]
    build/rehearse-move.sh tunnel <login> <homeserver port>
    build/rehearse-move.sh down
    build/rehearse-move.sh rented <address> --key <file> [--login <user>] [--machine-file <file>] [--order-time <UTC>]
        [--zone <name>] [--pool ubuntu,fedora [--pool-accounts <n>]] [--jobs <n>] [--org <program> --org-key <public key file> --person <login> --person-agent <socket>
        --central-token <program> --project <name> [--repository <name>] [--retire-host <host>]
        [--provider-keys <directory>]]

`rented` runs a move on a server the operator rented: it claims the server, checks it, runs `up`
and, on every exit, the host's `down`, and writes one line per step to a report directory outside the checkout, one per run.
`--pool` names the systems of a VM pool, ubuntu and fedora at most once each, with 1 to 8 accounts each from
`--pool-accounts` (unset 1); `--jobs` sets the forge's job capacity from 1 to 16. Both go into the host's inventory as
`porelo_host_vm_pool` and `forge_runner_capacity`, and the check is asked for KVM and the pool, so a server that cannot
hold them is refused before `up`. Without them the host has no pool and the forge its own job count.
Without the phase 2 options it stops after `up`. With them it also:

- adds the organization operator's public key (`--org-key`, one ssh-ed25519 key; its comment is dropped) to root's
  keys in `/etc/ssh/authorized_keys/root`, the file `up` made, unless root takes it already: `org host refresh` logs
  in as root, and a follow later writes the host admins' keys there;
- puts the host into the test organization as `rented`, through `<program> org host ...` run here (a wrapper that
  runs `porelo` as the test identity, whose `--version` the report keeps in `org-client.version`): it takes `--retire-host` off first, then adds `rented` with the person as its
  admin, files its card (the address, ssh port 22, the host key pinned at the first connection, forge ports 3000 and
  3001), and carries the project;
- has `org host refresh` hand the organization's token to the host, and waits for the follow to admit the person to
  the project, read from `porelo-host org status --json`;
- logs in as the person through their agent alone (`--person-agent`, no key files), gives the stop a new vault on
  standard input from a passphrase made for the run, mints the person's forge token, and stores the central token
  that `--central-token` prints in the vault as `<forge>.central`; neither secret is on a command line or in the
  report;
- checks as root that the host runs the packaged `porelo-host` and that no old host program is installed, nor named
  by a unit or a sudo rule (`host-program`);
- plays the story tests, which play each story once as a person would, each one executable
  `build/rehearse-steps/story-*`, by the same
  contract: a story's last line, `<story> passed`, `<story> waiting on <issue>, ...` (77) or `<story> failed at <step>:
  ...`, goes to `<report>/stories` with its exit and to the steps as `STORY <name> <line>`, and never ends the
  rehearsal (`story-st31` plays a key pasted at `vault put`'s prompt through a terminal, and a provider Pi does not
  know; `story-st41` a sample Maven checkout drafted by `project init`, read again once its parent is in the local
  repository; `story-st320` fresh checkouts of porelo-buildtools, porelo-planner and porelo from `PORELO_STORY_FORGE`,
  default `https://github.com/porelo-ai`, read for where the work tools and the native-image checks live;
  `story-st326` the packages of porelo-agy, porelo-codex, porelo-message-matrix, the window and porelo downloaded from
  the host's own repository and unpacked, each THIRD-PARTY-NOTICES held to the package's bill, and the IntelliJ
  plugin's zip from `PORELO_STORY_PLUGINS`, default the snapshots channel's `updatePlugins.xml`; `story-st346` a
  scratch repository of this one's issues whose head loses its size and then gets a rank of null, refused by the
  shared-rules step on the checkout and by the prepush's gate on a `git archive` of the commit, each naming the file
  and the field, with `porelo-release` resolved by `build/pom.xml` and the host's JDK, `PORELO_STORY_JAVA_HOME`;
  `story-st40`, only on a host with the forge and a machine pool, porelo's and the four agent adapters' workflows
  read for a provider named and a leg that asks for no kind, their newest legs on main on the host's forge, in the
  organization `PORELO_STORY_FORGE_ORG` or the project's, and on GitHub through its public API);
- runs the steps others build, each one executable under `build/rehearse-steps/`, in the order `tasks`, `busy-room`,
  `judge`, `window`; a step not on the branch is `SKIP <name> not built yet`, and `busy-room` and `judge`, which use
  the tasks `tasks` starts, are skipped when `tasks` is;
- pulls and pushes the project with central, and keeps `porelo host central-state --json` in the report;
- has the person push by the project file's name, by the central name and by an unknown name (64), then with a wrong
  central token in the vault, which must end in `refused authentication (HTTP 401)`, and puts the real token back
  (`refused-token`);
- with `PORELO_REHEARSAL_HOLD_FILE` set, makes that file after push-pull and keeps the host up until it is removed, so
  another run on the same host goes on first; the hard stop still ends the hold and runs `down`;
- with `PORELO_REHEARSAL_HOLD_FILE` set, also holds the host after a failed step from `up` on (`HOLD failure`), so it
  is fixed on the same server: removing the file runs `down`; writing `<hold file>.resume` instead makes the run start
  this checkout's script again (`RESUME`), which reruns `up` and then the failed step and the steps after it (the
  project step too when a later one failed, since the rerun `up` is followed again), and holds again on a new failure.
  The resume file is a plain file of the run's own account; it is empty or names new packages, one
  `PORELO_HOST_DEB=<absolute path>` line and, beside it only, one `PORELO_HOST_PACKAGES=<absolute path>` line; any
  other line, or a script that is not executable, is refused with `FAIL resume`, the host staying held. The hard stop
  ends a failure hold as any other;
- before `down`, takes the project off `rented` and has the host follow that as root while the organization still
  lists it (`org-follow`), so the persons' project memberships are gone, since `down` refuses a host where any are left;
  then takes `rented` out of the organization, and names it if that fails.

A step under `build/rehearse-steps/<name>` runs once, in its own process, with standard input at `/dev/null`, the
checkout root as its directory and umask 077. It is given, in the environment alone and nothing secret:
`REHEARSAL_STEP`, `REHEARSAL_HOST` (the address), `REHEARSAL_HOST_NAME` (`rented`), `REHEARSAL_HOST_KEY` and
`REHEARSAL_KNOWN_HOSTS` (the host key pinned at the first connection), `REHEARSAL_PERSON`, `REHEARSAL_PERSON_AGENT` (the
person's agent socket, the only identity), `REHEARSAL_ORG` (the program running `porelo` here as the test identity),
`REHEARSAL_CENTRAL_TOKEN` (the path of the program that prints the central token, never the token: a step runs it into a
pipe only), `REHEARSAL_PROJECT`, `REHEARSAL_REPOSITORY`, `REHEARSAL_PROVIDER_KEYS` (the directory of the providers' test
keys, read into a pipe only), `REHEARSAL_REPORT` (where it writes only `<name>.*`), `REHEARSAL_DEADLINE` (the hard stop
in Unix seconds) and `REHEARSAL_PERSON_SSH` (`build/rehearse-person-ssh.sh`, which runs one command on the host as the
person, each argument quoted, standard input forwarded); the run's own environment, such as the window step's
`REHEARSAL_WINDOW_VM`, `REHEARSAL_WINDOW_VM_KEY` and `REHEARSAL_WINDOW_CHECKOUT`, reaches it too. Beside it,
`$REHEARSAL_REPORT/org-status.json` holds the host's last `porelo-host org status --json` answer, written by the
`project` step when the follow admitted the person: who is an active person of the project, read by `busy-room` to tell
the project's own people from strangers. Its exit is its answer: 0 is `OK`, 77 is `SKIP` with its last printed line as
the reason, anything else `FAIL`, held like any failed step; both its streams go to `<report>/<name>.log`. The read keys
at central are taken off by the operator's own script.

Besides its three pi tasks, `tasks` starts a fourth, `rehearsal-all`, with porelo's `--all-repositories`, prompt-less
and detached on the host. It checks that the task sees every repository `porelo project show` names as a non-empty
`/workspace/<repository>/` without `.git`, that a write there is refused, that it has no git remote and no variable for
a gate or a push, and that after its stop and removal no task, container, volume or workspace directory of it is left.
A porelo that does not know the option makes that part a `SKIP` line with porelo's own words, and the step stays `OK`.

`start` makes one domain `porelo-host-rehearsal-<time>`, by default with 8 vCPUs, 16 GiB and an 80 GiB disk. It installs the collection
built from the checkout and runs `porelo.host.up` on the VM with the forge on, no VM pool and no KVM asked; `up`'s lines stay
on the VM in `/root/rehearsal-up.lines`. Without `--machine-file`, the organization is Molecule's stand-in on the
host's own forge, and nothing outside the machine is touched. With it, the file is the machine file a person's interface
writes for a real organization, and the follow puts the host's read keys on that organization's repositories, where
they stay until the repositories' owner removes them, as for any host. `start` refuses while any rehearsal's domain or
volume is still there. A failed or interrupted `start` deletes what it made and exits 1 naming anything libvirt still lists.
`up` is believed only by its lines: none failed, none waiting, and its summary of the host written.
The move check requires `PORELO_HOST_PACKAGE_VERSION` to name the pinned Debian host version and reads
`porelo-host --version` with a clean environment. A different version fails the check; source-script text is not evidence.

`--bare` stops once the VM answers ssh, as a provider hands a server over, and prints its host key's fingerprint. Its own account's key is also pinned where the host's sshd reads keys after `up`, so `ssh` keeps its way in. A
person then prepares it in the interface's *Prepare a server* on its address. The bootstrap line the dialog shows runs
in the VM's own account, reached with `build/rehearse-move.sh ssh`, and from then on the interface logs in as root and
runs `up` itself. Such a host is taken down by the interface; `down` here then only deletes the VM.

`ssh` logs in as the VM's admin with the run's own key and host key. `tunnel` runs `build/room-tunnel.sh` to the VM for an
admitted login, accepting only the run's host key, and stops once `down` has removed it. `down` runs
`porelo.host.down` on a running VM first, as on a rented host, and keeps the VM when that fails. It then deletes the
VM, its disk and its seed by the name its `start` recorded, believes that only once libvirt lists no rehearsal, and
removes the run's files under `target/rehearsal`.
