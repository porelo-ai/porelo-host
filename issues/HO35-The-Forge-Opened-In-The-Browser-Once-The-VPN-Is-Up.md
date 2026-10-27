# HO35 — The Forge Opened In The Browser Once The VPN Is Up

**Status:** Idea.

**What must be true.** Once the interface has brought the VPN up, the person opens `https://forge.porelo.internal/` in
their browser and signs in with a password they chose in the interface: no `/etc/hosts` line, CA import or password
file by hand. A stolen copy of the host's CA can vouch for no name outside `porelo.internal` and the VPN's network.

## Why

Today, after the VPN, the person runs a script for the name (an `/etc/hosts` line under sudo), imports `ca.pem` into
Firefox by hand, fetches a first password from a file on the host, changes it at the first sign-in and deletes both
copies. Each step exists because nothing on the person's computer knows the host's name, CA or person yet; the
interface's VPN step already runs as root once and already reaches the host over ssh, so it can bring all three.

## The shape

Read in the code, nothing measured; porelo-frontend's part is Frontend's to analyse.

- **The name: one `/etc/hosts` line in the interface's VPN step, not split DNS.** The root step of
  `porelo-frontend` (`lib/src/app/host_vpn.dart`) writes a marked line `10.73.0.1 forge.porelo.internal` next to
  `/etc/wireguard/porelo.conf` and removes it when the tunnel goes. Split DNS on the `porelo` link
  (`resolvectl domain porelo ~porelo.internal`) needs a resolver answering on `10.73.0.1:53`, a service the host does
  not run today, for one name; it pays off only when more names come.
- **The CA: name-constrained here, installed there.**
  - `roles/forge/tasks/tls.yml` makes the host's CA with
    `nameConstraints=critical,permitted;DNS:porelo.internal,permitted;IP:10.73.0.0/255.255.255.0` (the VPN's network
    from `vpn_address`). A CA made before is made again once, which takes the forge's certificate with it, as the task
    already does at expiry. Trusting the CA then cannot let the host vouch for another site.
  - The interface fetches `/etc/porelo-host/forge/ca.pem` over ssh (a certificate, no secret) and, in the same root
    step, puts it into the system store (`/usr/local/share/ca-certificates/porelo-host.crt`, `update-ca-certificates`)
    and Firefox's enterprise policy (`/etc/firefox/policies/policies.json`, `Certificates.Install`).
- **The password: the person's own, set over ssh, no file.** The interface asks for it once and pipes it over ssh into
  a root-only script on the host, which hands it to Forgejo's admin API on standard input (`PATCH
  /api/v1/admin/users/operator`, `must_change_password: false`).
  [HO29](HO29-The-Persons-Own-Web-Login-On-The-Forge.md)'s generated first password and its file go. The password is
  in no file, argument, variable or log on either side.
- **Weighed and not proposed:**
  - **Forgejo's reverse-proxy authentication** (the person signed in by their WireGuard peer). WireGuard does prove
    the peer's address, but the forge sits behind rootless podman's port forwarding, where every client may arrive
    with the same source address; then any job or task on the host that sets the header becomes `operator`, an owner
    who can merge, which is the approval porelo-project
    [PJ61](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj61) rests on. It also needs a
    proxy that terminates TLS in place of `systemd-socket-proxyd`.
  - **OIDC from the vault:** no identity provider exists to build on; several days across repositories.
  - **A passkey:** it can follow a first password but does not replace one; Forgejo can take one after this issue.
  - **A certificate from a public CA:** needs a domain of the person's and a DNS provider's token on the host for
    the ACME challenge, a secret and an account the product does not have.
- **What stays by hand:** restarting Firefox once after the policy is written; the first sign-in; a browser other
  than Firefox (Chromium's store is per user, `certutil` on `~/.pki/nssdb`); the agents' forge tokens of the test
  setup, which are for this computer's agents, not the person.
- **Touches:** [HO29](HO29-The-Persons-Own-Web-Login-On-The-Forge.md) (its first password goes),
  `doc/local-forge.md`, `roles/forge/README.md`; the CA's trust in jobs
  ([HO30](HO30-The-Forges-Trust-And-Job-Bounds-Measured.md)) is unchanged, since every name they reach lies inside the
  constraint.
- **Size, guessed until Analyzed:** here S (the constraint, the password script, Molecule checks that a certificate for
  another name signed by the CA fails `openssl verify`, and that the password set over stdin signs in); in
  porelo-frontend about M (the root step, the ssh fetch, the password dialog, and undoing all of it at `down`).

## To be checked

- That snap Firefox on Ubuntu 26.04 reads `/etc/firefox/policies/policies.json` and installs the certificate from a
  path the snap can read, and honours the name constraint.
- Whether rootless podman's port forwarding on the host keeps a client's source address, which decides how wrong the
  reverse-proxy option above would be.
