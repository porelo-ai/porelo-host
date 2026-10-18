# porelo-host

<img src="doc/images/early-bird.svg" width="350" alt="Early bird - work in progress">

> **Early bird - work in progress.** Porelo is not stable yet: until release 1.0.0, its code, commands
> and file formats can change without notice.

Brings a Porelo project up on a server and takes it down again, owned or rented by the hour: an Ansible
collection. From the project's `project.yml`, its repositories' own files and the person's file for the machine,
it sets up the host - packages, the VPN, KVM, the forge, the homeserver, Porelo and its account - restores the
data the project keeps, and starts the tasks; at down it copies that data off and leaves the machine to be given
back. What keeps a guarantee stays Porelo's: the playbook calls Porelo's own commands for following a signed
project, depositing keys and starting tasks.

**The collection has no role yet**: it builds and is checked, and its roles are planned in
[its issues](issues/README.md).

**Requirements**: `ansible-core` 2.19 or newer on the person's machine, which runs the playbook over ssh; a host with
Ubuntu 26.04; Porelo in the version the collection's own carries (`0.5.1-snapshot` follows Porelo 0.5.1). It is
installed from the tarball a release attaches, `ansible-galaxy collection install porelo-host-<version>.tar.gz`.

**Documentation: [porelo-ai.github.io](https://porelo-ai.github.io)**, all of Porelo's documentation in one site.

[Contributing](CONTRIBUTING.md), and [reporting a vulnerability](SECURITY.md).
