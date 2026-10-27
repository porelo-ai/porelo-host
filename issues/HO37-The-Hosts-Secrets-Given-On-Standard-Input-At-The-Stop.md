# HO37 — The Host's Secrets Given On Standard Input At The Stop

**Status:** Analyzed.
**Size:** L - every need of the stop changes, the stop runs as root, the VPN's key and the central token leave the
drive, and the stop's standard input is a contract porelo-frontend builds against, with [HO35](README.md#ho35) waiting
on it.

**What must be true.** At a host's stop a terminal on the desktop, where `keepassxc-cli` alone unlocks the person's
`secrets.kdbx` and the interface holds no secret, gives the host every secret the stop needs in one pipeline on standard
input, and the host passes each straight to what uses it. The drive holds no secret in the clear, and once `up` has
ended to its last step no secret given at the stop lies in a file on the host but the VPN's key in `/etc/wireguard`.
This is the host's part of porelo-project
[PJ51](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj51).

## Plan

Read in the code, nothing measured. The file holds a group `shared` (the lasting forge CA, the forge's password, the
drive's login) and a group per host under `hosts/<name>` (its WireGuard key, its vault passphrase, the machine file's
keys); a host gets only its own group and `shared`.

- **One pipeline, as root.** The terminal the interface opens runs `keepassxc-cli` into `ssh <admin>@<host> sudo
  porelo-host-stop --stdin [--email ADDRESS] NEED...`, as `up` itself is run, with the needs as the stop's line names
  them, and writes one line per secret: `<need> [<name>] <value in base64>`. Base64 keeps a secret from breaking the
  framing; the script refuses an unknown need, a second line of one need and name, or a value that does not decode, with
  exit 64, before it uses any line. A named need the lines do not bring is asked in the terminal where there is one (the
  one-time code, a first host's passphrase), and refused where there is none. `--stdin` refuses to run but as root; the
  script stays installed as today, `/usr/local/bin`, `0755`, root's, and without `--stdin` it is the person's terminal
  stop as the account, unchanged. As root it reads the account's name and `vpn_private_key_path` from
  `/etc/porelo-host/stop.conf`, no secret, root's `0644`, which `roles/porelo/tasks/install.yml` writes from the
  inventory, and refuses where the file is missing or names an account `getent` does not know.
- **Where each goes.** Each value is decoded through a pipe (`printf '%s' | base64 -d |`) into its user, never a
  here-string, which bash may put into a temporary file; it lives only in the script's memory and that pipe:
  - `drive`: the Tresorit password into `tresorit-cli login --email ADDRESS --password-on-stdin`, the address (no
    secret) from `--email`, run as Porelo's account through `runuser -u <account>` with `XDG_RUNTIME_DIR` set to that
    account's, the environment the terminal stop has today by being that account;
  - `vault-new`, `vault`: into `porelo vault init|unlock --passphrase-stdin`, as the account;
  - `key <name>`, one line per key, with the need `keys`: every key of the host's group, put after the vault opens into
    `porelo vault put <name>`, as the account. `keys` is named with `vault-new`; a vault that exists holds its keys, and
    `roles/porelo/tasks/project.yml` keeps only a check that each `porelo_vault_keys` entry is in the vault, refusing
    with the entry's name where it is not, and `--from-file` goes;
  - `wireguard`: into `vpn_private_key_path`, now `/etc/wireguard/porelo-host.key`, root `0600`, for the host's life,
    removed at `down`. wg's `PostUp` reads it at every start of the interface, so a restart or a reboot keeps the VPN,
    which [HO22](README.md#ho22)'s ssh behind the VPN needs. Ubuntu's AppArmor profile lets wg read `/etc/wireguard`, so
    the local rule goes. **An accepted risk**, written into `doc/decisions.md` with the change: the key lies in the
    clear on the host's disk, where the host's root and the provider's disk images can read it, as on any WireGuard
    server. It stays because a key lost at a reboot locks the person out once ssh is behind the VPN. It would change if
    WireGuard could take its key from a sealed store, or if a reboot no longer needed the VPN to reach the host;
  - `forge-central-token`: not a need of the first play, since whether repositories are still to migrate is known only
    once the forge runs. `roles/forge/tasks/repositories.yml` refuses, naming `forge-central-token`, where a repository
    is to migrate and `/run/porelo-host/forge-central.token` is missing, as it refuses a missing file on the drive
    today; such a terminal gives it with `porelo-host-stop --stdin forge-central-token` and runs `up` again. The token
    waits in that root `0600` file on the tmpfs until the migration removes it in an `always`, or `down` does. The
    exposure: where that `up` fails before the forge's migration, the token stays there, root's alone, until the next
    `up` takes it, `down` or a reboot;
  - [HO35](README.md#ho35)'s `forge-certificate`, no secret: the certificate the desktop signed, with the CA's; the CA's
    key never reaches the host.
- **The stop's needs, all known in the first play, before the drive is synced:** `drive`, `vault-new` with `keys`,
  `vault` (`roles/porelo/tasks/needs.yml`); `wireguard` while neither `vpn_private_key_path` exists nor `ip link show
  wg-porelo` finds the interface (iproute2 is there before the vpn role installs `wireguard-tools`), so the resumed `up`
  does not stop again, from a new `roles/vpn/tasks/needs.yml` that `playbooks/up.yml` includes as `porelo.host.vpn` with
  `tasks_from: needs`, so the role's defaults load. A key or token missing later is refused by its user, named, and
  given by another `--stdin` call; there is no second stop.
- **The stop's line keeps `v` 1:** `wireguard` and `keys` are new values of `needs`, which a reader that does not know
  them skips (`doc/lines.md`).
- **The terminal stays** for what the file does not hold: `porelo-host-stop` without `--stdin`, run by the person as the
  account, works as today.
- **Touches:** `playbooks/up.yml` (the vpn's needs), `roles/porelo/files/porelo-host-stop` (`--stdin`),
  `roles/porelo/tasks/install.yml` (`stop.conf`), `needs.yml`, `project.yml`, `down.yml`, `roles/porelo/README.md`,
  `meta/argument_specs.yml` (`project` no longer reads keys from the drive), `roles/vpn/tasks/needs.yml` (new),
  `key.yml`, `down.yml`, `roles/vpn/defaults/main.yml`, `meta/argument_specs.yml` (the `needs` entry point,
  `vpn_private_key_path`), `README.md`, `templates/apparmor-local-wg.j2` and its handler, which go, `doc/decisions.md`
  (the accepted risk); `roles/forge/tasks/repositories.yml`, `down.yml`, `roles/forge/defaults/main.yml`,
  `meta/argument_specs.yml`, `README.md` (`forge_central_token_path`), `doc/lines.md`, and `AGENTS.md`'s reason for the
  stop script, which now also runs as root.
- **Red first, in Molecule:** with a test key and passphrase the scenario makes, one `--stdin` pipeline at the first
  stop opens the vault, puts the key, and brings the VPN up; a line of an unknown need or bad base64 is refused before
  the vault is touched; the `up` that first names repositories refuses naming `forge-central-token`, and after a
  `--stdin forge-central-token` call the next `up` migrates and leaves no token file; once `up` has ended, a search of
  the host's files, journal and `up`'s output for each value finds it only in the vault and `vpn_private_key_path`.

## Acceptance

- A whole `up` on a fresh host runs with nothing typed but the one-time code and the master password on the desktop.
- The drive's folder holds no `wireguard.key`, token or key file, and `up` reads none from it.
- After an `up` that ended to its last step, `/run/porelo-host/` is empty, and the VPN comes back after a reboot.

## To be checked

- Whether `tresorit-cli login --password-on-stdin` reads the one-time code from the terminal or from standard input,
  which decides whether the pipeline can carry the password while the person types the code.
- With porelo-frontend, whose stop is fed from the file: the line format, the entries' names in `secrets.kdbx`, and that
  the pipeline runs as the admin with sudo.
