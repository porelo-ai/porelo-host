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
- **Driven by `porelo-host`, decided:** `porelo-host up` rents through the module and then sets the host up, and
  `porelo-host down` sets it down and then runs `tofu destroy`, one command each as today. `--given ADDRESS
  --host-key` stays for a machine one has, which `tofu` never touches. porelo-frontend's counterpart, replacing
  `packages/porelo_host`'s own Scaleway calls, is its own issue, named here once it is filed.
- **The contract `porelo-host` reads**, which changes only with both repositories:
  - inputs as `TF_VAR_project`, `TF_VAR_scaleway_project_id`, `TF_VAR_zone`, `TF_VAR_offer`,
    `TF_VAR_ssh_public_key` in `tofu`'s environment;
  - the secrets only in that environment: `SCW_SECRET_KEY` (with `SCW_ACCESS_KEY`) and the state's encryption in
    `TF_ENCRYPTION`, never an argument or a file;
  - the calls: `tofu -chdir=<module> init -input=false -lockfile=readonly`, then `apply -input=false -auto-approve`,
    then `output -json`; at `down`, `destroy -input=false -auto-approve`, then `plan -detailed-exitcode` reading no
    change as the check that nothing is left;
  - outputs, read from `tofu output -json`: `address` (the first IPv4), `host_key` (`ssh-ed25519 <base64>`), trusted
    as today's tag, and `server_id`;
  - a second `up` finds the server in the state and changes nothing, as today's find by tag does.
- **How the module reaches the administrator's computer:** in the release beside the collection's tarball, as
  `porelo-host-tofu-<version>.tar.gz` holding `tofu/scaleway/` with its `.terraform.lock.hcl`, under the same
  `SHA256SUMS`; `porelo-host` takes the release's own file and refuses any other, as it does the collection.
- **Which `tofu` runs:** `porelo-host` finds `tofu` on `PATH` and refuses it, before anything is rented, unless
  `tofu version -json` names the one version the module pins; the module's `required_version` refuses any other too.
  The providers come by `tofu init` from the registry, checked against the lock file's hashes.
- **`down`'s last step:** with the module, `porelo-host down` plays `porelo.host.down` first and keeps the host when
  the play does not finish, as today; only a finished play, or `--give-back-anyway`, runs `tofu destroy`.
- **The state, decided:** it lies in the person's drive (today a Tresorit tresor), in a folder per project,
  encrypted by OpenTofu's own state encryption, `aes_gcm` with a `pbkdf2` key, `enforced` so a plain state is
  refused. Its passphrase lives in the system's secret store (Secret Service, Keychain, Credential Manager) beside the
  Scaleway key, and reaches `tofu` only in `TF_ENCRYPTION`; never a file, an argument or the tresor. On another
  computer the passphrase is entered once, into that computer's store. The state holds the host's private key and
  the server's id, so it never lies anywhere unencrypted.
- **Two computers on one state:** OpenTofu's local lock does not reach across a synced folder, so `porelo-host` guards
  it itself, at the provider, which every computer sees at once: before `apply`, a server carrying the project's tag
  that the state does not hold refuses `up`, naming it ("another computer rents this project's host, or this
  computer's drive is not synced yet"); `tofu` never rents a second one. A copy of the state that the drive's client
  made in a conflict (a file beside it named as a conflict) refuses both `up` and `down` until a person keeps one. A
  lease file beside the state, naming the computer and the time, makes a second `up` during the first say whose it
  is, but the provider's tag is the guard.
- **A drive not synced yet:** a state missing or older than the provider says is caught the same way: `up` finds a
  tagged server the state lacks and refuses, and `down` with no server in the state but a tagged one at the provider
  refuses rather than giving back nothing, both naming the drive. Nothing is rented or destroyed on a state the
  provider contradicts.
- **Pinned:** `required_version` to one OpenTofu version; the `scaleway/scaleway` and `hashicorp/tls` providers by
  exact version, with `.terraform.lock.hcl` committed holding their hashes for `linux_amd64`, `darwin_arm64` and
  `windows_amd64`. The operator installs that OpenTofu version from its release, checked against its published
  checksum; nothing here installs it.
- **Tests without renting first:** `tofu fmt -check`, `tofu validate` and `tofu test` with mocked providers, holding
  the tags, the cloud-config's host key, the outputs and the refusal of a missing offer or key; in the Build from a
  pinned OpenTofu image, as the Ansible tools run from theirs. **One real rent, decided in principle:** one Elastic
  Metal for about an hour, once the module is built and green without renting; the Scaleway project and the moment
  are the operator's word then, asked in the channel with the plan (what runs, how long, how nothing is left).
- **Built by** Codex `gpt-6.1-sol` `high` from this plan, the module and its tests here, the driving in
  porelo-frontend's own issue; the state's encryption and the handling of the two secrets
  reviewed by Codex `xhigh`.
- **Red first:** `tofu test` against a module without the project tag, and with a plain state accepted.

## Acceptance

- `tofu test` passes without renting, and fails on a module that drops the project tag or the host key's tag.
- On the operator's word: `porelo-host up` rents one machine through the module and brings it up, `porelo-host down`
  sets it down and destroys it, and the Scaleway project lists nothing of it afterwards.
- The state on disk reads as encrypted, and OpenTofu refuses it without the passphrase.

## To be checked

- That `scaleway_baremetal_server` takes a cloud-config and tags as the API does, and that its create waits for the
  install to complete; read in the pinned provider's documentation and its source.
- The current OpenTofu release whose state encryption and mocked providers in `tofu test` are both available.
- How Tresorit's client names a conflict copy, so the refusal finds it; measured with two clients on one tresor.
