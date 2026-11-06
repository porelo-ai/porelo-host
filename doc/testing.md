# Testing the collection

The collection's roles are tested on a VM made for the run, never in a container and never on a machine another run
uses: a role installs packages, KVM and system services, and only a fresh machine shows what it did.

    build/molecule.sh

runs the Molecule scenario `extensions/molecule/default` against such a VM, through libvirt on the machine it is
started on (`qemu:///system`, pool `images`, network `default`). It needs libvirt, `qemu-img`, `virt-install`,
`xorriso`, ssh and podman there; Molecule itself runs from the image `build/tools-image` pins.

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
and `verify` reads on the machine what `up` promises. The run's own files stand in for what the person keeps on the
desktop: the secrets file's values under `/root`, given to the stop on standard input, and the machine file, uploaded into the host's setup directory as the interface does.

**In the Build** the same script runs on GitHub's runner, after the linters and the tarball, on `main` and on the
project's own pull requests: about three minutes, the runner adding libvirt by pinned versions first.

**How long it takes**, measured on this project's workstation (16 threads, AMD): about a minute from start to clean-up
with the image cached - 52 s for a run whose `up` has no role yet, of which the VM takes about 15 s to answer ssh.
The first run on a machine also downloads the image, 825 MB, about 70 s at the measured 12 MB/s.

## Rehearsing a move

An agent's move can be rehearsed before a host is rented, on a VM made the same way on the development machine:

    build/rehearse-move.sh start [--machine-file <file>]
    build/rehearse-move.sh ssh [<command>...]
    build/rehearse-move.sh tunnel <login> <homeserver port>
    build/rehearse-move.sh down

`start` makes one domain `porelo-host-rehearsal-<time>` with 8 vCPUs, 16 GiB and an 80 GiB disk. It installs the collection
built from the checkout and runs `porelo.host.up` on the VM with the forge on, no VM pool and no KVM asked; `up`'s lines stay
on the VM in `/root/rehearsal-up.lines`. Without `--machine-file`, the organization is Molecule's stand-in on the
host's own forge, and nothing outside the machine is touched. With it, the file is the machine file a person's interface
writes for a real organization, and the follow puts the host's read keys on that organization's repositories, where
they stay until the repositories' owner removes them, as for any host. `start` refuses while any rehearsal's domain or
volume is still there. A failed or interrupted `start` deletes what it made and exits 1 naming anything libvirt still lists.
`up` is believed only by its lines: none failed, none waiting, and its summary of the host written.

`ssh` logs in as the VM's admin with the run's own key and host key. `tunnel` runs `build/room-tunnel.sh` to the VM for an
admitted login, accepting only the run's host key, and stops once `down` has removed it. `down` runs
`porelo.host.down` on a running VM first, as on a rented host, and keeps the VM when that fails. It then deletes the
VM, its disk and its seed by the name its `start` recorded, believes that only once libvirt lists no rehearsal, and
removes the run's files under `target/rehearsal`.
