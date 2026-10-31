# HO76 — Each Push Judged When It Arrives

**Status:** Review; blocked by [HO71](README.md#ho71), [HO75](README.md#ho75).
**Size:** L - a hook in the forge's container, a root socket judge with Porelo's commit verify in an isolated unit, an
append-only record and sync's arming; the image has no glibc, so Porelo runs on the host.
**Blocked by:** [HO71](README.md#ho71), [HO75](README.md#ho75); Porelo's commit verify against signers and KRL.

Part of the project's decision that a person joins with one click: one SSH key per person, no VPN, the state signed in
Git on the central forge, every service on the host behind a Unix socket.

**What must be true.** The first accepted push of a commit to the host's forge is its arrival: there it is judged
against the signers and the KRL in force, with no `valid-before` key, and the verdict is recorded.

- A pre-receive hook asks Porelo to verify each new commit and task signature against the project's own allowed signers
  and the KRL now in force, task signatures through their recorded certificates; a commit that fails is refused, naming
  it.
- Each accepted commit's verdict, with the arrival time and the signing key's fingerprint, is recorded append-only on
  the host, readable by the project's persons.
- The bring's migration is not an arrival: the hook is armed right after it, and the history the repository holds then
  is recorded as `migrated`, not judged here. Only later pushes are arrivals. Judging a migrated history under the
  rules of its own time needs a history mode of Porelo's commit verify, an idea of Porelo's own.

## Tests

- a commit Porelo refuses is refused with its lines and recorded nowhere; a good one is recorded with its time and
  signer; any other answer, a request from another peer or of a path outside the pushed repository refuses unjudged;
  the hook takes only 200; a migrated history is recorded once as `migrated`.

## Acceptance

- [ ] a push signed by a revoked key, or by an expired task certificate, is refused at the forge, naming the commit;
- [ ] a good push lands and its commits are in `arrivals <project> <repository>` with the arrival time and signer;
- [ ] after a bring, every repository is armed and its migrated history is recorded as `migrated`;
- [ ] a person of another project reads no arrivals of this one.

## Plan

- `roles/forge/files/porelo-forge-pre-receive`, mounted read-only into Forgejo's container at
  `/usr/local/libexec/porelo/pre-receive`, posts the hook's lines, the repository and its quarantine with `curl` to
  `/run/porelo-host/verify/verify.sock` (mounted at `/run/porelo-verify`), shows the answer and passes only on 200.
- `porelo-host-verify.socket` (the forge account's alone, `0600`, `Accept=yes`, listening before Forgejo starts) runs
  `porelo-host-person verify-push` per connection, under a shared lock of `forge.conf` and a 30-second bound on each
  read. It answers only the forge account's peer, reads one request with one `Content-Length` and well-formed update
  lines, passes a push that only deletes refs unjudged, maps `/var/lib/gitea/` into the forge volume with no link on
  the way, refuses a repository of no registered project or a quarantine, object or alternate path not of that
  repository, and runs `porelo commit verify --json` with `systemd-run` as the forge account, `PrivateNetwork`, `ProtectHome=tmpfs`,
  the repository bound read-only, the quarantine variables set, and the signers, certifiers, KRL and certificates as
  credentials staged in its own directory under `/run/porelo-host/push`. The keys in force come from the project's
  signer state, expired cards left out; the certifiers sign the project's own tasks alone, and only the project's task
  certificates valid now are passed.
- 0 with every commit accepted appends one line per commit to root's
  `/var/lib/porelo-host/arrivals/<project>/<repository>.jsonl` under a lock and answers 200; 65 answers 403 with
  Porelo's printable lines; anything else 500.
- `sync` arms, through `podman exec forgejo`, each repository of the organization, dot names too, refusing one without
  Forgejo's own executable hook: it links the hook first, then lists the history of each repository whose record has
  no `armed` line, records the commits not yet there as `migrated` and then the `armed` line. `arrivals <project> <repository>`
  answers the record to root or a person of the project, through a sudo rule. `down` removes the units, the hook and
  the records.
- Forgejo's own hook runs before the judge; a push the forge refuses after both keeps its verdict line; a repository made on
  the forge another way is judged from the next sync on.
- Red first: `tests/unit/roles/test_porelo_host_person_tasks.py` (the judge, its refusals, arming, reading) and
  `tests/unit/roles/test_forge_push_judge.py` (the hook script with a curl stand-in, the units, mounts, sudo, down).
  The VM run waits for [HO74](README.md#ho74), whose push tasks rewrite Molecule's push.
