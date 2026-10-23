# Decisions

What was decided for the collection and why, so that it is not decided again. Each row names what holds; the section
says why.

| Subject | What holds | |
|---|---|---|
| The Ansible tools | They run from one image pinned by digest, through podman, here and in the Build. | [Why](#the-ansible-tools) |
| Where the collection ships | A tarball attached to the repository's GitHub releases; Ansible Galaxy later. | [Why](#where-the-collection-ships) |
| The systems | Ubuntu 26.04 at first; another system is an issue of its own. | [Why](#the-systems) |
| Where the playbook runs | On the host itself, with Ubuntu's own `ansible-core` and `-c local`. | [Why](#where-the-playbook-runs) |
| The order of `up` and `down` | The drive comes before the VPN, around one stop for the person; the store's last copy is to come before `vault clear`. | [Why](#the-order-of-up-and-down) |
| Where the VM test runs | On a libvirt VM per run everywhere: here, in the GitHub Build and in the Forgejo build. | [Why](#where-the-vm-test-runs) |
| `ansible-test sanity` | Not run yet, though the collection holds Python; it comes in its own pinned container. | [Why](#ansible-test-sanity) |
| Tresorit's installer | Run only when signed under a pinned CA, whose fingerprint was read from the installer itself. | [Why](#tresorits-installer) |
| Ubuntu's `ansible-core` and CVE-2026-89091 | An accepted risk: the one tarball the host installs is the collection's own. | [Why](#ubuntus-ansible-core-and-cve-2026-89091) |
| The changelog | `CHANGELOG.md`, Keep a Changelog, as in every Porelo repository; no `antsibull-changelog`. | [Why](#the-changelog) |

## The Ansible tools

`ansible-core`, `ansible-lint`, `yamllint` and `molecule` come from `ghcr.io/ansible/community-ansible-dev-tools`,
named by digest in `build/tools-image` and run by `build/tools.sh`. Nothing of Ansible is installed on a machine that
checks the collection, and the Build and a local check run the same versions. A tag alone is refused, since it could be
moved to another image under the same name. The image is moved by this repository's agent; Dependabot moves only the
workflows' actions.

## Where the collection ships

Nobody outside the project installs it yet, and Galaxy needs an account for the namespace `porelo`. A tarball on the
GitHub release is enough for the one project that uses it; Galaxy comes once others do.

## The systems

Ubuntu 26.04 is the system the project rents its host with. Each further system, Fedora first, is a file of platform
variables in each role and a Molecule scenario, so it is an issue of its own rather than a branch in every task.

## Where the playbook runs

`host up`, porelo-frontend's command, copies the collection's tarball and the inventory to the host over ssh, installs
`ansible-core` from Ubuntu's packages and runs the playbook there with `-c local`. The person's computer needs only ssh
and `host up`, on Linux and Windows alike: on Windows Ansible's control node does not run, and on neither can podman
be assumed. The `ansible-core` the host's Ubuntu carries is therefore the version the collection is held to.

## The order of `up` and `down`

The drive comes before the VPN because the host's WireGuard key lies on the drive, and so the person has one stop for
both the Tresorit login and the vault; until the VPN is up, the host is reached over its public ssh only. At `down`,
`porelo vault clear` on an account with its own homeserver also runs the transport's `clear`, which removes the
homeserver's database volume, its port, its registration token and its poll positions. So the store, which no role
keeps yet, is to take its last copy before `vault clear`, and at `up` to be restored before the first
`porelo task start`, which would otherwise make a fresh homeserver.

## Where the VM test runs

The roles install packages, KVM and system services, so they are tested on a fresh VM, never in a container. GitHub's
hosted runner `ubuntu-24.04` offers KVM (an AMD CPU with `svm`, `/dev/kvm`, `kvm_amd`), and a probe ran
`build/molecule.sh` green there: the VM answered after 17 s, and the job took about three minutes. Forgejo builds with
the same workflows, so one test runs the same in all three places, with no rented machine. The Build runs it on `main`
and on the project's own pull requests, never on a fork's, whose code would run on this repository's runner. The
packages the runner adds are pinned by version; a version the archive no longer carries stops the Build, and the pins
are moved by hand.

## `ansible-test sanity`

The collection holds Python: the `lines` callback and the `tresorit_installer` module. `ansible-test sanity` is not
run on them yet, since it installs its own requirements from PyPI at run time, by version and without a hash, which a
pinned build may not do. Until it runs in a pinned container of its own, the Build checks them with `black`, a
compile, and unit tests that run each under the image's own `ansible-playbook`; what sanity adds beyond that, such as
the module's documentation against its arguments, is not checked.

## Tresorit's installer

**What holds.** Tresorit serves one Linux installer at a fixed address and replaces it without notice, so it cannot
be pinned by its digest. Its line 2 is an RSASSA-PSS SHA-512 signature over everything from line 3 on, and line 3 is
the signing certificate with the CA that issued it. The role runs the installer only when that CA's SHA-256
fingerprint is the pinned one, the CA issued the certificate, the certificate is made for code signing and valid
now, and the signature covers the file as it is; the installer's own `CHECKSUM` is a CRC and is not relied on.

**Where the pin comes from.** The fingerprint of "Tresorit Code Signing CA 2020" was read from the installer as
Tresorit's site serves it, fetched twice by separate ways, by curl here and in the operator's browser, both
byte-identical. Tresorit publishes no fingerprint that could be read instead. The CA's root, "Tresorit Root CA 2014",
is not in the file.

**What would change the answer.** A fingerprint Tresorit publishes, which then replaces the one read; a new CA when
this one expires on 2029-12-31, which stops the role, naming the pinned fingerprint, until the pin is read again
in the same way.

## Ubuntu's `ansible-core` and CVE-2026-89091

**The exposure.** The host runs the plays with Ubuntu 26.04's own `ansible-core` 2.20.1, for which Ubuntu lists
CVE-2026-89091 without a fix: `ansible-galaxy collection install` checks a tarball's member paths without following
symbolic links, so a crafted collection tarball can write outside the directory it is installed into. `host up`
runs exactly that command, as root, on the host.

**Why it stays.** The one tarball the host installs is this collection's own, built by `ansible-galaxy collection
build` from a clean clone at a pushed commit and refused by `build/check-tarball.sh` if it holds a dot file or
anything outside the paths the collection ships. A crafted tarball would have to be ours.

**What would change the answer.** A tarball from anywhere but this repository's release, an install from Ansible
Galaxy, or Ubuntu shipping a fixed `ansible-core`, which the host then takes as it is.

## The changelog

One form of changelog across the repositories: entries go under `[Unreleased]` in the same commit as the change.
`antsibull-changelog` would be a second form beside it.
