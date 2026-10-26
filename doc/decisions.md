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
| The release's publish job unpacks the build's artifact | An accepted risk: `unzip` parses an archive the build job made, beside the token that writes the release. | [Why](#the-releases-publish-job-unpacks-the-builds-artifact) |
| The changelog | `CHANGELOG.md`, Keep a Changelog, as in every Porelo repository; no `antsibull-changelog`. | [Why](#the-changelog) |
| An agent is installed from Porelo's catalogue as it is | Every package named as kind `agent` is installed; the catalogue reads every apt source on the host. | [Why](#an-agent-is-installed-from-porelos-catalogue-as-it-is) |
| Porelo's setup script | It comes in the `porelo` package from Porelo's apt repository, which the role adds by its pinned fingerprint. | [Why](#porelos-setup-script) |
| The forge's accounts | Forgejo and its runner run as `porelo-forge` and `porelo-runner`, never as Porelo's account. | [Why](#the-forges-accounts) |
| Whether the forge runs | A host setting, `porelo_host_forge`, written by the interface beside the account; Porelo changes nothing for it. | [Why](#whether-the-forge-runs) |
| How a job publishes to the registry | With the account `porelo-publisher`'s package token, an organization Actions secret, on every branch. | [Why](#how-a-job-publishes-to-the-registry) |
| No push mirrors | The forge pushes nothing to the central forge; the gathered push is a plain `git push` without force. | [Why](#no-push-mirrors) |
| The same workflows on both forges | GitHub's workflows run unchanged on the forge; only variables and secrets differ. | [Why](#the-same-workflows-on-both-forges) |

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
anything outside the paths the collection ships. A crafted tarball would have to be ours. Each release attaches
that tarball with a `SHA256SUMS` naming its digest, built once by the release workflow, so a person's `host up` can
take exactly the release's own file and refuse any other.

**What would change the answer.** A tarball from anywhere but this repository's release, an install from Ansible
Galaxy, or Ubuntu shipping a fixed `ansible-core`, which the host then takes as it is.

## The release's publish job unpacks the build's artifact

**The exposure.** `.github/workflows/release.yml`'s job `publish` holds the token that writes the release. It runs
`unzip` on the artifact its job `build` uploaded, and `build` runs a checkout, the tools image and a fetched action. A
`build` made to do harm shapes that archive, so only an unknown flaw in `unzip`'s parsing would let it run code
beside the token.

**Why it stays.** The job runs nothing of the artifact: it checks `SHA256SUMS`, refuses anything but the tarball and
that file, and attaches them; `check-actions` holds the job to runner commands, four env names and expressions only in
`env` and `if`. Downloading the artifact without unpacking it would take an action fetched beside the token, which is
the exposure the split into two jobs removes.

**What would change the answer.** A known flaw in Ubuntu's `unzip` that runs code from an archive, or a way to fetch
the artifact's files one by one with `gh` alone.

## The changelog

One form of changelog across the repositories: entries go under `[Unreleased]` in the same commit as the change.
`antsibull-changelog` would be a second form beside it.

## An agent is installed from Porelo's catalogue as it is

**What holds.** The role installs every package the setup script's catalogue names as kind `agent`. The catalogue
reads every apt source on the host.

**The exposure.** A package in another source on the host that declares `Provides: porelo-agent` is included.

**Why it stays.** On a host, porelo-host itself writes the sources: Ubuntu's archive and Porelo's pinned one.
Predicting apt's choice from `apt-cache policy` was shown unsound.

**What would change the answer.** Porelo's catalogue binding the install to its own source, after which the role
needs no change.

## Porelo's setup script

The role adds Porelo's apt repository only once the downloaded signing key has the fingerprint Porelo's
`getting-started.md` pins, installs `porelo` from it, and runs `/usr/share/porelo/setup/porelo-setup.sh` from that
package for the account and the extra packages, rather than fetching an unpinned script or keeping a copy here.

## The forge's accounts

A task's container must not share a user namespace with what holds the forge's admin and the person's central token,
and a job's code must reach neither. So Forgejo runs as `porelo-forge` and its runner as `porelo-runner`, each with
linger and subordinate ids of its own; only `porelo-runner` is in `kvm`, since a job may drive a VM.

## Whether the forge runs

The forge belongs to the machine, not to a project: `porelo_host_forge` (default `false`) is written by the interface's
`host up` into the first inventory, beside the account. A project's file asks for nothing, so Porelo needs no change.

## How a job publishes to the registry

A run's own token cannot write the organization's registry: Forgejo answers `401` from its package access check,
measured on Forgejo 17. So `up` makes the account `porelo-publisher`, in a team that writes the organization's packages
and nothing else, and sets its token as the organization's Actions secret `PORELO_PUBLISHER_TOKEN`. Every build
publishes its snapshots with it, an unreviewed task branch's too; the token stays in Forgejo and the runner's jobs and
reaches no task.

## No push mirrors

Forgejo's push mirror force-pushes: with commit A on central `main` and B on the host's, a sync answered `200` and A was
gone, measured. So the role configures none. Work leaves through the gathered push, a plain `git push` without force,
which refuses when the central forge moved.

## The same workflows on both forges

A workflow that branches on the forge it runs on is tested on one of them only. So the runner offers GitHub's labels on
an image close to GitHub's, takes actions from github.com by their pins and offers the JDK as `JAVA_HOME_25_X64`, and
the organization holds the variables and placeholder secrets the workflows read; snapshots go to the forge's own Maven
registry. Where the forges still differ, a job sees it: the runner sets `JAVA_TOOL_OPTIONS` for the host's trust store,
and the repositories are private.
