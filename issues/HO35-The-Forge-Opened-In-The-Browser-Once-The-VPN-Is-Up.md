# HO35 — The Forge Opened In The Browser Once The VPN Is Up

**Status:** Analyzed; blocked by [HO37](README.md#ho37).
**Size:** M - a first-play step and three forge task files, a need of [HO37](README.md#ho37)'s stop and a password
script, and the stop's contract porelo-frontend reads.

**What must be true.** Once the interface has brought the VPN up, the person opens `https://forge.porelo.internal/` in
their browser and signs in with their own lasting password: no `/etc/hosts` line, CA import or password file by hand, on
the first host or any later one. The CA the person's computer trusts is one for all their hosts, and a stolen copy of
its key can vouch for no name outside `porelo.internal` and the VPN's network.

## Why

Today, after the VPN, the person runs a script for the name (an `/etc/hosts` line under sudo), imports `ca.pem` into
Firefox by hand, fetches a first password from a file on the host, changes it at the first sign-in and deletes both
copies. Each new host makes a new CA, so the import and the password come again on every host. The interface's VPN step
already runs as root once and already reaches the host over ssh, so it can bring all three, and a CA and a password that
outlive the host make it once.

## Plan

Read in the code, nothing measured; porelo-frontend's part is analyzed in that repository.

- **The name: the interface's VPN step writes a marked `/etc/hosts` line** `10.73.0.1 forge.porelo.internal` and removes
  it at `down`. Split DNS on the `porelo` link waits until several names or hosts come, since it needs a resolver on
  `10.73.0.1:53` the host does not run.
- **One lasting CA, made once on the person's desktop, not on a host.** It carries
  `nameConstraints=critical,permitted;DNS:porelo.internal,permitted;IP:10.73.0.0/255.255.255.0`, `CA:TRUE,pathlen:0` and
  lives ten years. Its key and its certificate are entries of the `shared` group of the person's `secrets.kdbx`
  ([HO37](README.md#ho37)); nothing of it lies on the drive, and the host reads nothing of it from there.
- **The host keeps no CA key on disk.** `roles/forge/tasks/tls.yml` stops making `/etc/porelo-host/forge/ca.key`. A new
  first-play step, `roles/forge/tasks/request.yml`, included from `playbooks/up.yml` as `porelo.host.forge` with
  `tasks_from: request` where `porelo_host_forge` is set, as root, since the forge's accounts come only in the second
  play. A certificate holds where it ends in more than 30 days, names `forge_address` (the checks `tls.yml` makes today)
  and matches its key. Where neither the forge's `tls/forge.pem` nor one waiting in `/etc/porelo-host/forge/` beside its
  key holds, it makes a key and a certificate request there, the key root `0600`, keeping a key already waiting from a
  run that stopped, and names `forge-certificate` in `porelo_host_needs`; the resumed `up` finds the certificate the
  stop wrote waiting and asks nothing. `tls.yml` moves a waiting key and certificate, never copies them, into the forge
  account's `tls/`, so one copy of the key is on the host, and leaves the forge's own pair alone when nothing waits.
  `ca.pem` stays where `trust.yml`, the runner's bundle and the VM pool read it today.
- **The certificate at [HO37](README.md#ho37)'s stop:** `porelo-host-stop --request`, run as root like the `--stdin`
  pipeline, prints the request (no secret); a `forge-certificate` line brings the forge's certificate and the CA's,
  which the stop checks against the request's key and the constraint before it writes them. Who signs is the open
  question below.
- **The person's password: lasting, set on every new forge, in no file.** `roles/forge/tasks/person.yml` makes
  `operator` with a random password it discards, as `admin.yml` does, and no `person.password`; [HO29](README.md#ho29)'s
  first password and its file go. A root-only script, `/usr/local/sbin/porelo-host-forge-password`, run by the admin
  over ssh with sudo, reads the password from standard input into one `python3 -I` process, makes a token of
  `write:admin` for itself with Forgejo's command line, sends `PATCH /api/v1/admin/users/operator` with
  `must_change_password: false` as a JSON body on curl's standard input, and deletes the token; the shared admin token
  keeps its scopes. The password lives only in that process's memory: in no file, argument, Ansible variable, register
  or log. The interface runs it once `up` has ended, since the forge runs only in the second play.
- **The first host:** where standard input is a terminal, the script asks the password twice, unechoed, compares the two
  in memory and sets it. Where it is kept after that is the open question below.
- **Installed once:** the interface's root step puts the CA's certificate into the system store
  (`/usr/local/share/ca-certificates/porelo-host.crt`) and Firefox's policy (`/etc/firefox/policies/policies.json`,
  `Certificates.Install`) only where that certificate, compared by its SHA-256, is not already there. A new host then
  changes nothing on the desktop but the `/etc/hosts` line.
- **The key's longer life, weighed.** A stolen key vouches, to every client that trusts it, for any name under
  `porelo.internal` and any address in `10.73.0.0/24`, for ten years, and for no other site, since the constraint is
  critical. That reaches the person's forge on every host, not one: whoever holds the key and the person's traffic can
  stand in for the forge and read the password and pushes. Kept only in `secrets.kdbx`, unlocked on the desktop, it is
  as safe as that file. There is no revocation: a key seen stolen is replaced by a new CA, which the interface installs
  in place of the old, compared by its SHA-256, and every forge's certificate is signed again at its next stop. The
  interface warns 90 days before the CA ends and makes the next one the same way.
- **Weighed and not proposed:** Forgejo's reverse-proxy authentication (rootless podman's port forwarding may give every
  client one source address, so any job setting the header becomes `operator`, the approver porelo-project
  [PJ61](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj61) rests on); OIDC from the vault (no
  identity provider exists); a passkey (it follows a first password, it does not replace one); a public CA's certificate
  (a domain and a DNS provider's token on the host).
- **What stays by hand:** restarting Firefox once after the policy is first written; a browser other than Firefox; the
  agents' forge tokens of the test setup.
- **Touches:** `playbooks/up.yml`, `roles/forge/tasks/request.yml` (new), `tls.yml`, `person.yml`, `down.yml` (removes
  `porelo-host-forge-password` as it removes `porelo-host-push`; `/etc/porelo-host/forge` and `tls/` go as today),
  `roles/forge/meta/argument_specs.yml` (the `request` entry point; `forge_person` no longer names a password file),
  `roles/forge/README.md`, `roles/forge/files/porelo-host-forge-password` (new) and its install task,
  `roles/porelo/files/porelo-host-stop` (`--request`, `forge-certificate`), `doc/local-forge.md`, `doc/lines.md`,
  `AGENTS.md`'s list of files that cannot be Java; the CA's trust in jobs ([HO30](README.md#ho30)) is unchanged, since
  every name they reach lies inside the constraint.
- **Red first, in Molecule:** a certificate for `example.org` signed by a test CA with the same constraint fails
  `openssl verify`; `forge-certificate` refuses a certificate for another key; a fresh `up` stops naming
  `forge-certificate`; the password piped into `porelo-host-forge-password` signs in to the API and appears in no file
  under `/etc`, `/var`, `/run`, `/home` or `/srv`, the journal or the run's output.

## Acceptance

- On a second host, the person opens the forge with no import, prompt or password change, and Firefox shows the
  certificate under the one CA.
- A certificate for a name outside `porelo.internal`, signed by the CA, is refused by `openssl verify` and Firefox.
- No `ca.key` and no `person.password` exist on the host; a search of the host's files, journal and `up`'s output for
  the password finds nothing.

## Open questions

- **Who signs the forge's certificate.** (a) The interface gives the stop the CA's certificate and its key, and the host
  signs with `openssl x509 -req -CA ca.pem -CAkey /dev/stdin`, writing the key nowhere; simple for the interface, but
  root on every rented host sees the key while it signs, and a host taken over keeps it. (b) Recommended: the interface
  fetches the request with `--request`, signs it on the desktop and gives back the certificate; the key never leaves the
  desktop. The decision taken so far carries the key to each host; (b) would change it.
- **Where the lasting password is kept after the first host.** The decision so far keeps it out of the interface; the
  shape of `secrets.kdbx` keeps it in that file, which only the interface unlocks and feeds to the host. Either (a) the
  interface asks it once, writes it into `secrets.kdbx` and pipes it to each host, or (b) the person adds it to
  `secrets.kdbx` in KeePassXC and the interface pipes it from there. Both hold it in the interface on every later host.

## To be checked

- That snap Firefox on Ubuntu 26.04 reads `/etc/firefox/policies/policies.json`, installs the certificate from a path
  the snap can read, and honors the name constraint.
- That Forgejo's admin API changes a password with a token of `write:admin`, refuses one without it, and that `forgejo
  admin user generate-access-token` and the API's token deletion do what the plan reads.
