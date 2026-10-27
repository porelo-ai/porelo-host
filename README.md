# porelo-host

<img src="doc/images/early-bird.svg" width="350" alt="Early bird - work in progress">

> **Early bird - work in progress.** Porelo is not stable yet: until release 1.0.0, its code, commands
> and file formats can change without notice.

Brings a Porelo project up on a server and takes it down again, owned or rented by the hour: an Ansible
collection. From the project's `project.yml`, its repositories' own files and the person's file for the machine,
it sets up the host - packages, the VPN, KVM, the forge, the homeserver, Porelo and its account - restores the
data the project keeps, and installs every offered agent; the person starts tasks and signs agents in as needed.
At down it stops every running task of the account, copies that data off and leaves the machine to be given
back. What keeps a guarantee stays Porelo's: the playbook calls Porelo's own commands for following a signed
project and depositing keys.

The [host lifecycle](doc/index.md) explains setup and teardown. The [local forge](doc/local-forge.md) explains
how task work is built and accepted locally, and which steps toward central publication remain unbuilt.

**Requirements**: a host with Ubuntu 26.04; the playbook runs on the host itself, with the `ansible-core` Ubuntu
carries (2.20; the collection needs 2.19 or newer), so the person's computer needs only ssh. Porelo in the version
the collection's own follows (`0.5.5`, Porelo 0.5.1, its snapshots until Porelo releases it). It is
installed from the tarball a release attaches, `ansible-galaxy collection install porelo-host-<version>.tar.gz`.

**Documentation: [porelo-ai.github.io](https://porelo-ai.github.io)**, all of Porelo's documentation in one site.

[Contributing](CONTRIBUTING.md), and [reporting a vulnerability](SECURITY.md).
