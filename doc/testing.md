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
`~/.porelo/cache/`, and its base volume `porelo-host-base-<digest>.qcow2` in the pool.

**The VM** is Ubuntu 26.04 from the cloud image `build/test-image` pins by URL and SHA-256, 4 vCPUs and 4 GB, with the
host's CPU passed through so KVM runs inside it, as on a rented host. Its ssh host key is made for the run and is the
only one accepted.

**What the scenario does** is what `host up` does on a host: Ubuntu's own `ansible-core`, the collection installed from
its tarball, and `porelo.host.up` run on the machine itself with `-c local`. A second converge must change nothing,
and `verify` reads on the machine what `up` promises.

**How long it takes**, measured on this project's workstation (16 threads, AMD): about a minute from start to clean-up
with the image cached - 52 s for a run whose `up` has no role yet, of which the VM takes about 15 s to answer ssh.
The first run on a machine also downloads the image, 825 MB, about 70 s at the measured 12 MB/s.
