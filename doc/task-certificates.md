# Task certificates and host tokens

The root helper accepts a task certificate through `sudo porelo-host-person task <task>`. Standard input is bounded
at 16 KiB and contains one Ed25519 SSH user certificate. Task names match `[a-z0-9][a-z0-9._-]{0,63}`.
OpenSSH reads the certificate from a private temporary file and verifies its signature. Its signing CA must be the
calling person's current, unrevoked key in `/etc/porelo-host/organization/applied.json`. Its one principal
is `task:<project>:<task>`, with `default` for a task without a project, and its validity must include the current
time and have a finite end. The project must be one the person is a member of on this host.

Before anything is recorded, Porelo judges the same certificate by its own rules: `porelo task check-certificate
--task <task> --login <login> --keys <file> --krl <file> --json`, given the certificate on stdin. It runs in a
throwaway systemd unit with a dynamic user, no network and no home. Its only files are the person's key in force and
the host's KRL, staged under `/run/porelo-host/sync` and removed afterwards. It checks the key id `porelo task <task>
by <login>`, the one principal, the five default extensions and no critical option, and the validity bound of the
start. A refusal is shown on stderr and refuses the task. An answer for another task key, signer or project than the
host read is refused with exit 69.

The certificate is recorded once in `/var/lib/porelo-host/tasks/<login>/<task>.json`, owned by root with mode 0600
inside mode 0700 directories. The record includes its canonical certificate line, task key fingerprint, signer,
principals, key ID and validity. The certificate comment is discarded. Another certificate cannot replace the record,
and a fingerprint cannot name two tasks. Retrying the same certificate replaces the token for that task.

On a host running Forgejo, a successful start answers the task's token alone on stdout, with no newline. The consumer
must capture this answer directly in the host gate, outside the task container; never display or log it. The helper
writes no token file. On a host without Forgejo it records the certificate and answers no token.
`sudo porelo-host-person task --end <task>` deletes only the named task's token and leaves the certificate record.
`sudo porelo-host-person task --show <fingerprint>` answers the JSON record to any unlocked admitted person, or root.
Missing records are refused. Other non-token answers are JSON lines, and refusals go to stderr with nonzero status.

The daily persistent `porelo-host-task-sweep.timer` runs root's `porelo-host-person sweep`, deleting tokens whose
recorded certificates have expired. It skips hosts without `forge.conf`. One person's API failure does not prevent
the remaining deletions; any failure still returns nonzero. Expiration cleanup can lag until the daily sweep runs.

Admission creates the person's forge users without tokens. `sudo porelo-host-person forge-token` replaces all tokens
of the calling person's forge login but its lends younger than a day and answers one token alone on stdout: the person's token, which
their vault keeps as `<forge>.person`. `sudo porelo-host-person forge-token --lend` makes a lend beside it, a token for
one of Porelo's commands named `porelo-host-lend-<UTC time>-<uuid>`, deletes only the login's lends a day old or
older, and answers it the same way. A lend left over until then reaches no more than the person's own token, of
the same login and scopes, and lies in no file, so Porelo's gate commands and task starts leave the vault's token valid and two
commands at once each keep their own. Lock, the last membership's removal, purge and revocation delete every token. Its scopes are `write:repository`,
`write:issue`, `write:organization` and `read:user`; organization and user access support the person's own forge calls.
Task tokens belong to `porelo-<login>`, have distinct names and use `write:repository` and `read:package`, the
latter so a task resolves its project's snapshots. The existing token-generation command supplies API scopes with no
repository or organization selector. Repository write and package read reach every organization whose teams name that
forge identity, a task of the default project's too; the gate must restrict use to the project and repository
certified for the task. A token scope alone
does not provide that gate restriction. The pinned server's additional token restriction options remain unverified.

Organization revocation locks the account, ends its sessions and deletes every token of the person's forge users after
recording the applied state. An API failure is reported and the next organization intake retries it. A failed service
revocation leaves the local record locked, so a follow cannot restore host access. Lock, last-membership removal
and purge retain their all-token revocation paths. Lock and purge remove legacy token delivery directories without
following links.

Porelo's task start is the consumer: it keeps the answered token in the task's vault entry for its gate, which pushes
as `porelo-<login>` on the host's loopback. The host keeps no lasting gate token.

Push, pull and migration take the person's token from `sudo -n porelo-host-person forge-token` at each run; Porelo's
own commands on the host's forge ask for `--lend`. Each puts it into the vault entry `<forge>.person` at once for the person's own tools, since it
replaces the one before. No stop
waits for an identity's token any more.

## Test mode

A measuring or test host has no person who could certify a task. For such a host alone, root sets test switches:
the person entry of the `porelo` role writes `porelo_host_test_switches` to `/etc/porelo-host/test-mode.json`, and
`down` always takes it away. The file is a regular file owned by root, mode 0600, holding `{"v": 1, "switches":
[...], "why": "..."}`. `switches` is an open set: the host program acts only on the names it knows, and a file that is
missing, of another `v`, unreadable, a link or not root's means no switch at all. The role refuses a name the host
program does not know. While a switch is on, `up` says it on a note line of its own, `TEST MODE`.

A person asks for the switches with `sudo porelo-host test-switches --json`, which answers `{"switches": [...]}`. The
first switch is `start-uncertified`: while it is on, `porelo-host task start <task>` with an empty standard input
starts the task without a certificate. Porelo warns and asks first, and `--yes` answers for it. Without the switch,
the host refuses such a start with 65, whatever Porelo asks. The host program's side is Porelo's.

The measuring role sets `start-uncertified` in its own inventory only, so its throwaway developers start their stub
tasks; it writes no person record.
