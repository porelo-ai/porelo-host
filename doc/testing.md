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

**The VM** is Ubuntu 26.04 from the cloud image `build/test-image` pins by URL and SHA-256, 4 vCPUs and 4 GB, with the
host's CPU passed through so KVM runs inside it, as on a rented host. Its ssh host key is made for the run and is the
only one accepted.

**What the scenario does** is what `host up` does on a host: Ubuntu's own `ansible-core`, the collection installed from
its tarball, and `porelo.host.up` run on the machine itself with `-c local`. A second converge must change nothing,
and `verify` reads on the machine what `up` promises. Local packages arrive before the first up. The run's machine
file is uploaded into the host's setup directory as the interface does; no removed stop wrapper is invoked.

**In the Build** the same script runs on GitHub's runner, after the linters and the tarball, on `main` and on the
project's own pull requests: about three minutes, the runner adding libvirt by pinned versions first.

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
        [--zone <name>] [--org <program> --person <login> --person-agent <socket> --central-token <program>
        --project <name> [--retire-host <host>]]

`rented` runs a move on a server the operator rented: it claims the server, checks it, runs `up`
and, on every exit, the host's `down`, and writes one line per step to a report directory outside the checkout, one per run.
Without the phase 2 options it stops after `up`. With them it also:

- puts the host into the test organization as `rented`, through `<program> org host ...` run here (a wrapper that
  runs `porelo` as the test identity): it takes `--retire-host` off first, then adds `rented` with the person as its
  admin, files its card (the address, ssh port 22, the host key pinned at the first connection, forge ports 3000 and
  3001), and carries the project;
- has `org host refresh` hand the organization's token to the host, and waits for the follow to admit the person to
  the project, read from `porelo-host org status --json`;
- logs in as the person through their agent alone (`--person-agent`, no key files), gives the stop a new vault on
  standard input from a passphrase made for the run, mints the person's forge token, and stores the central token
  that `--central-token` prints in the vault as `<forge>.central`; neither secret is on a command line or in the
  report;
- pulls and pushes the project with central, and keeps `porelo host central-state --json` in the report;
- after `down`, takes `rented` off the project and out of the organization, and names it if that fails.

The judge step, a commit made inside a task and pushed to its own branch and to another, is not built yet; the report
says `SKIP judge`. The read keys at central are taken off by the operator's own script.

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
