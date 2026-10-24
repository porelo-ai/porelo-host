# HO23 — A Machine Rented And Given Back By OpenTofu

**Status:** Analyzed.
**Size:** L - a new tool in this repository (an OpenTofu module, its pins and its tests), the state's encryption, and
a hand-over to porelo-frontend's `porelo-host` that crosses repositories; Scaleway first, Hetzner later on the same
pattern.

**What must be true.** An administrator rents a machine at a provider and gives it back by one OpenTofu module per
provider, whose state is kept encrypted with the administrator, so that Porelo's hosts can be had from more than one
provider and from a company's own tooling, outside the interface.

## Why

- Renting and giving back a host is today `porelo-host`'s, a Dart package of porelo-frontend, for Scaleway alone.
- porelo-project [PJ40](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj40) names OpenTofu as
  the planned extension "for Porelo as a product for others", likelier than an adapter per provider in each language,
  and it runs on Linux, macOS and Windows.
- Setting a machine up and taking it down are the `host-admin` role's (porelo-project's issue of the roles), and may
  happen entirely outside Porelo; a module the administrator runs keeps them there, beside this repository's
  collection that sets the host up once it is rented.

## Plan

- **What it replaces, read in porelo-frontend's `packages/porelo_host`:** Elastic Metal in `fr-par-1`, offer
  `EM-I220E-NVME`, Ubuntu 26.04; the server found first by its tag `porelo-project=<project>`, so a second run rents
  nothing; the person's ssh key looked up in the Scaleway project, never registered; an ed25519 host key made for the
  machine, its private half in cloud-init (`ssh_deletekeys`, `ssh_genkeytypes: [ed25519]`) and its public half in a
  tag `porelo-host-key=`, trusted from the tag alone; readiness until the server and its install are done and it has
  an IPv4; giving back refused unless the server carries the project tag. No security group, private network or IPv6.
- **The module, `tofu/scaleway/`**, one directory, resources and inputs from the same values the dialog asks:
  - inputs: `project` (the tag and the name), `scaleway_project_id`, `zone` (default `fr-par-1`), `offer` (default
    `EM-I220E-NVME`), `ssh_public_key` (the person's, looked up, never created);
  - `tls_private_key` (ed25519) makes the host key; `scaleway_baremetal_offer` and `scaleway_baremetal_os` look up
    the offer and Ubuntu 26.04 and refuse when absent or out of stock; `scaleway_iam_ssh_key` looks up the person's
    key; `scaleway_baremetal_server` with the cloud-config, the two tags and the key;
  - outputs: `address` (the first IPv4), `host_key` (`ssh-ed25519 <base64>`), `server_id`.
- **The hand-over to the host's own part:** the administrator runs `tofu apply`, then
  `porelo-host up --given <address> --host-key "<host_key>"`, an option `porelo-host` already has for a machine one
  has. So nothing of porelo-frontend changes for `up`. Giving back is `porelo-host down`, its play first, then
  `tofu destroy`, which waits until the server is gone; `tofu plan -detailed-exitcode` then reading no change is the
  check that nothing is left.
- **The state, encrypted with the administrator:** OpenTofu's own state encryption, `aes_gcm` with a `pbkdf2` key
  from a passphrase, `enforced`, so a plain state is refused. The configuration comes from the environment
  (`TF_ENCRYPTION`), never a file or a command line; the Scaleway key reaches the provider as `SCW_SECRET_KEY` in the
  environment, read from the administrator's store. The state holds the host's private key and the server's id, so
  it is never committed and never leaves the administrator's machine unencrypted.
- **Pinned:** `required_version` to one OpenTofu version; the `scaleway/scaleway` and `hashicorp/tls` providers by
  exact version, with `.terraform.lock.hcl` committed holding their hashes for `linux_amd64`, `darwin_arm64` and
  `windows_amd64`. The operator installs that OpenTofu version from its release, checked against its published
  checksum; nothing here installs it.
- **Tests without renting first:** `tofu fmt -check`, `tofu validate` and `tofu test` with mocked providers, holding
  the tags, the cloud-config's host key, the outputs and the refusal of a missing offer or key; in the Build from a
  pinned OpenTofu image, as the Ansible tools run from theirs. **One real `apply` and `destroy` on the operator's word
  only**, a rented Elastic Metal for about an hour, its cost named before.
- **Shipped** in the release beside the collection's tarball, its files under the same `SHA256SUMS`.
- **Built by** Codex `gpt-6.1-sol` `high` from this plan; the state's encryption and the handling of the two secrets
  reviewed by Codex `xhigh`.
- **Red first:** `tofu test` against a module without the project tag, and with a plain state accepted.

## Acceptance

- `tofu test` passes without renting, and fails on a module that drops the project tag or the host key's tag.
- On the operator's word: `tofu apply` rents one machine, `porelo-host up --given` with its outputs brings it up,
  `porelo-host down` and `tofu destroy` give it back, and the Scaleway project lists nothing of it afterwards.
- The state on disk reads as encrypted, and OpenTofu refuses it without the passphrase.

## Open questions

- **Who runs it:** the administrator apart, with `porelo-host up --given` after it (proposed), or `porelo-host up`
  calling `tofu` itself, which ties the interface to OpenTofu being installed?
- **Where the state and its passphrase live:** a directory per project on the administrator's computer and the
  passphrase in the administrator's password store (proposed), or the state in the operator's tresor?
- **The one real `apply`/`destroy`:** may it rent one Elastic Metal for about an hour, and in which Scaleway project?

## To be checked

- That `scaleway_baremetal_server` takes a cloud-config and tags as the API does, and that its create waits for the
  install to complete; read in the pinned provider's documentation and its source.
- Whether `porelo-host down` works with `--given`, or finds the server only by its tag at Scaleway; asked of Agent
  Frontend.
- The current OpenTofu release whose state encryption and mocked providers in `tofu test` are both available.
