# HO79 — A Person's SSH Login Confirmed By A Second Factor

**Status:** Idea (operator, 2026-10-31).
**Size:** - (M proposed, for the recommended form).

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** A person's SSH login to the host needs, beside their key, a second factor the host can check:
a stolen key file alone opens no session.

## Analysis

**How (TOTP).** `AuthenticationMethods publickey,keyboard-interactive:pam` in the `Match Group porelo-people` block of
`/etc/ssh/sshd_config.d/10-porelo-host.conf`, with `KbdInteractiveAuthentication yes` there only and a PAM stack of
its own for sshd that runs `pam_oath` (or `pam_google_authenticator`) after the key. Root, logging in with the pinned
host admin's key for `up`, and service accounts are not in `porelo-people` and stay key-only.

**Enrolment and storage.**

- The seed lies in root's `/var/lib/porelo-host/totp/<login>` (0600, in a 0700 directory), in `pam_oath`'s users file
  form. No person can read another's seed.
- A person enrols with `sudo -n porelo-host-person totp enrol` in their own session. It makes the seed, shows it once
  to that terminal (and as a QR code), and keeps it only after a correct first code. Renewal is the same call, which
  needs the current code.
- Root can read every seed. The host admin is root, so "no admin sees the seed" holds only for the process (no seed in
  a log, a post or the registry), never against root itself.
- Recovery without an admin handling the seed: the host admin puts a signed `totp=reset` for the person in the
  registry. The next login of that person is key-only once and leads straight to enrolment. A lost key and code
  together are a new admission, as today.

**What breaks.** Every SSH connection of a person asks for a code:

- the interface's calls;
- `porelo.host.bring`/`join` and `porelo-host up` run as the person;
- the Element and Porelo socket forwards;
- the sudo helpers called over SSH;
- tasks a person starts on the host over SSH.

A non-interactive call (`BatchMode=yes`) fails outright. One `ControlMaster` connection per session with
`ControlPersist` (for example 8 h) covers it: one code per working day, as long as the master lives. When the master
dies, the next call asks again, so the interface needs a code prompt and must route all its calls through the master.

**Alternatives.**

- **FIDO2 keys (`sk-ed25519`):**
  - a touch per connection, no seed on the host, and no PAM;
  - OpenSSH's `PubkeyAuthOptions touch-required` (or `verify-required` for a PIN) enforces it;
  - with a ControlMaster, one touch per session;
  - it needs a hardware key per person, and the card would carry an `sk-` key.
- **KeePassXC's confirmation (`ssh-add -c`):** a confirmation on the person's own machine for each use of the key.
  The host cannot check it, so it guards against a stolen agent, not a stolen key file.
- **TOTP only for the day's first login:** `pam_oath`'s window does not do that by itself. A PAM time stamp per person
  (as `pam_timestamp`) would let later logins within the day pass with the key alone. It is a weaker form of
  ControlPersist, with state on the host.

**Recommendation.**

- FIDO2 as the second factor where a person has a hardware key: the host only requires `touch-required` for keys of
  `sk-` type, no seed exists anywhere, and the card already carries the key.
- TOTP as described, for persons without one, with ControlMaster in the interface.
- Size M for TOTP: sshd and PAM settings, enrol/renew/reset in the person helper, the registry's reset flag, tests,
  the guide. FIDO2 alone is S on the host and needs the card and interface side.

## Open questions

- Which of the two michi wants first, and whether a person may choose.
- The interface's side, for TOTP (as Agent Frontend set it out, about M there):
  - the code is typed in a terminal the interface opens, never in a form of its own;
  - that terminal opens one ControlMaster per host;
  - every later call uses `ControlMaster=no` with `BatchMode=yes`, and fails at once with a line the interface
    recognises when the master is gone;
  - the host card's SSH config would carry `ControlPath` in the person's private runtime folder (for example
    `$XDG_RUNTIME_DIR/porelo/ssh/%C`) and `ControlPersist 8h`;
  - IntelliJ and the agents must use the same `ControlPath`.

  FIDO2 needs none of this in the interface.
