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

**Nothing is built here yet.** Its shape, and what outlives a machine, are planned in
[porelo-project's issues](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md).

**Documentation: [porelo-ai.github.io](https://porelo-ai.github.io)**, all of Porelo's documentation in one site.

[Contributing](CONTRIBUTING.md), and [reporting a vulnerability](SECURITY.md).
