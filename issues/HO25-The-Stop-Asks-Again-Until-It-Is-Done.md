# HO25 — The Stop Asks Again Until It Is Done

**Status:** Review.
**Size:** S - one shell script the porelo role installs, its Molecule test and the contract's page; porelo-frontend's
side is one call.

**What must be true.** At `up`'s stop, a mistyped Tresorit password or vault passphrase is asked again in the same
terminal on the host, the e-mail included, until it succeeds or the person cancels. A typo never costs a whole `up`
run, and the person always sees, in the terminal, whether the stop is done.

## Plan

- **Today:** porelo-frontend's `hostStopCommand` chains `tresorit-cli login … && porelo vault init` with `&&`. A failed
  login ends the session ("The session ended with 1"), and only a new `up` run of a few minutes brings the stop back.
- **`roles/porelo/files/porelo-host-stop`**, shell, installed by `roles/porelo/tasks/install.yml` as
  `/usr/local/bin/porelo-host-stop`, root's, 0755:
  - `porelo-host-stop [--email ADDRESS] NEED...`, each need one of `drive`, `vault-new`, `vault`. `--email` is
    allowed only with `drive`, and `drive` without it asks for the address. Anything else exits 64 with one plain
    line naming it.
  - `drive`: asks for the e-mail, showing the given one as the default to keep with Enter, and checks that it is a
    plain address. Then `tresorit-cli login --email <it> --password-on-stdin`, reading the terminal. On failure it
    prints the client's own error description and asks "Try again? [Y/n]", and the e-mail can be changed again.
  - `vault-new`: `porelo vault init`; `vault`: `porelo vault unlock`; both asked again on failure, as above.
  - The needs run in the order `drive`, then the vault, as `up` names them; the vault is not asked before the drive is
    logged in.
  - **Exit codes:** 0 when everything named is done, its last line "The host's stop is done; close this terminal,
    and setup goes on."; **75** when the person cancels (`n`, or Ctrl+C), its last line "Cancelled; the host waits at
    this stop. Running up again comes back here."; 64 for a wrong call; 69 when `tresorit-cli` or `porelo` is not
    found.
  - **No secret passes through it:** the client and the vault read theirs from the terminal. The script holds none,
    writes no file, and logs nothing.
- **`doc/lines.md`**, under *The stop*: the person's step is `porelo-host-stop` with the needs as `up` named them,
  with its exits.
- **`AGENTS.md`**'s files that cannot be Java: `roles/porelo/files/porelo-host-stop`, shell, since it runs on the host
  in the person's terminal, where there is no Java.
- **Test, `extensions/molecule/default/verify.yml`**, the script driven through a pseudo-terminal as the account, with
  the Tresorit stand-in refusing a password `wrong` with `CLIBadPasswordOrEmail`, as the real client does:
  - harm: a failed login must never go on to the vault or end with 0 (the person told "done" while the host still
    waits). A wrong password, then the right one, then a vault passphrase given twice differently and then twice the
    same, ends 0 with the client logged in and the vault made;
  - cancelling at the first failure ends 75, with the vault untouched and the client logged out;
  - an unknown need, and `--email` without `drive`, end 64 before anything runs;
  - red first: the test run against today's `&&` chain fails on the retry.
- **Release:** porelo-frontend calls the script only from the release that carries it, pinned by its digest
  (porelo-frontend's issue, its condition). So this is released as the collection's next version once it is in
  Review, and its tag is the operator's.

## Acceptance

- In Molecule, a mistyped password and a mismatched passphrase are each asked again in the same terminal, and the run
  ends 0 with both done; a cancel ends 75 with nothing done after it.
- Seen to fail first: the same test against the `&&` chain of today.
