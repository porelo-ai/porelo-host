# HO35 — The Forge Opened In The Browser Once The VPN Is Up

**Status:** Review.
**Size:** L - a first-play step and three forge task files, a need of [HO37](README.md#ho37)'s stop and a password
script, the stop's contract porelo-frontend reads, and every place of the Molecule scenario that signed in with the
first password (grown from M while building).

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
- **One lasting CA, made once on the person's desktop, not on a host,** in the terminal that has `secrets.kdbx` open,
  its key piped straight into the file. It carries
  `nameConstraints=critical,permitted;DNS:porelo.internal,permitted;IP:10.73.0.0/255.255.255.0`, `CA:TRUE,pathlen:0` and
  lives ten years. Its key and its certificate are entries of the `shared` group of the person's `secrets.kdbx`
  ([HO37](README.md#ho37)); nothing of it lies on the drive, and the host reads nothing of it from there.
- **The host never holds the CA's key.** `roles/forge/tasks/tls.yml` stops making `/etc/porelo-host/forge/ca.key`. A new
  first-play step, `roles/forge/tasks/request.yml`, included from `playbooks/up.yml` as `porelo.host.forge` with
  `tasks_from: request` where `porelo_host_forge` is set, as root, since the forge's accounts come only in the second
  play. A certificate holds where it ends in more than 30 days, names `forge_address` (the checks `tls.yml` makes today)
  and matches its key. Where neither the forge's `tls/forge.pem` nor one waiting in `/etc/porelo-host/forge/` beside its
  key holds, it makes a key and a certificate request there, the key root `0600`, keeping a key already waiting from a
  run that stopped, and names `forge-certificate` in `porelo_host_needs`; the resumed `up` finds the certificate the
  stop wrote waiting and asks nothing. `tls.yml` moves a waiting key and certificate, never copies them, into the forge
  account's `tls/`, so one copy of the key is on the host, and leaves the forge's own pair alone when nothing waits.
  `ca.pem` stays where `trust.yml`, the runner's bundle and the VM pool read it today.
- **The desktop signs, and the CA's key never leaves it.** At [HO37](README.md#ho37)'s stop, on the wire:
  - **The request:** `ssh <admin>@<host> sudo porelo-host-stop --request` prints the waiting request as one PEM block,
    `-----BEGIN CERTIFICATE REQUEST-----`, on standard output and nothing else (no secret), exit 0; 65 where no request
    waits.
  - **The signing:** in the terminal that has `secrets.kdbx` open, `openssl x509 -req` signs it with the CA's key on a
    pipe from `keepassxc-cli`. The desktop sets every extension itself and copies none from the request:
    `subjectAltName=IP:10.73.0.1,DNS:forge.porelo.internal`, `basicConstraints=critical,CA:FALSE`,
    `extendedKeyUsage=serverAuth`, 365 days. The host's address and name come from the inventory the interface wrote,
    never from the request.
  - **The answer:** a line `forge-certificate <base64>` in the `--stdin` pipeline, the base64 of two PEM blocks, the
    forge's certificate then the CA's. The stop writes them only where the certificate's key is the waiting key's, it
    verifies under that CA, it names `forge_address` and `forge_name`, it holds for more than 30 days, the CA carries
    the critical name constraint, and the CA is the one in `/etc/porelo-host/forge/ca.pem` where one is there; otherwise
    it refuses with exit 64, naming which check failed.
- **The person's password: lasting, set on every new forge, in no file but `secrets.kdbx`.**
  `roles/forge/tasks/person.yml` makes `operator` with a random password it discards, as `admin.yml` does, and no
  `person.password`; [HO29](README.md#ho29)'s first password and its file go. A root-only script,
  `/usr/local/sbin/porelo-host-forge-password`, run by the admin over ssh with sudo, reads the password from standard
  input into one `python3 -I` process, makes a token of `write:admin` for itself with Forgejo's command line, and sends
  `PATCH /api/v1/admin/users/operator` with `must_change_password: false` as a JSON body; the shared admin token keeps
  its scopes. Forgejo 17's command line deletes no token (measured on the pinned image; the API's token deletion is not
  measured), so the token is kept only in that process's memory and stays in Forgejo's store as a hash until `down`;
  root on the host commands the forge's admin anyway. On the host the password lives only in that process's memory: in
  no file, argument, Ansible variable, register or log. The terminal runs it once `up` has ended, since the forge runs
  only in the second play.
- **Kept in the file, never in the interface:** the master password is typed in a terminal on the desktop, where
  `keepassxc-cli` alone reads `secrets.kdbx` and pipes the password over ssh into the script. At the first host the
  person types the lasting password in that same terminal, and it goes into the file there; the interface holds neither.
- **Installed once:** the interface's root step puts the CA's certificate into the system store
  (`/usr/local/share/ca-certificates/porelo-host.crt`) and Firefox's policy (`/etc/firefox/policies/policies.json`,
  `Certificates.Install`) only where that certificate, compared by its SHA-256, is not already there. A new host then
  changes nothing on the desktop but the `/etc/hosts` line.
- **The key's longer life, weighed.** A stolen key vouches, to every client that trusts it, for any name under
  `porelo.internal` and any address in `10.73.0.0/24`, for ten years, and for no other site, since the constraint is
  critical. That reaches the person's forge on every host, not one: whoever holds the key and the person's traffic can
  stand in for the forge and read the password and pushes. Kept only in `secrets.kdbx`, unlocked on the desktop, it is
  as safe as that file. There is no revocation: a key seen stolen is replaced by a new CA, which the interface installs
  in place of the old, compared by its SHA-256; a host takes the new CA when it is set up again, since its stop keeps
  the CA it has. The interface warns 90 days before the CA ends, and the terminal makes the next one the same way.
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

## To be checked

Measured on a throwaway VM in the Molecule scenario, 2026-10-27 23:06Z to 23:28Z: Forgejo's admin API changes the
person's password with a token of `write:admin`, and the password signs in with no change asked.

- That snap Firefox on Ubuntu 26.04 reads `/etc/firefox/policies/policies.json`, installs the certificate from a path
  the snap can read, and honors the name constraint.
