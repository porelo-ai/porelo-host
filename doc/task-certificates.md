# Task certificates and host tokens

The root helper accepts a task certificate through `sudo porelo-host-person task <task>`. Standard input is bounded
at 16 KiB and contains one Ed25519 SSH user certificate. Task names match `[a-z0-9][a-z0-9._-]{0,63}`.
OpenSSH reads the certificate from a private temporary file and verifies its signature. Its signing CA must be the
calling person's current, unrevoked key in `/etc/porelo-host/registry/applied.json`. Its principals include
`task:<task>`, and its validity must include the current time and have a finite end. The certificate's other
principals and key ID are retained without interpretation; person, project and repository conventions still require
agreement with the producer.

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
of the calling person's forge login and answers one token alone on stdout. Its scopes are `write:repository`,
`write:issue`, `write:organization` and `read:user`; organization and user access support the existing bring.
Task tokens belong to `porelo-<login>`, have distinct names and use `write:repository`. The existing token-generation
command supplies API scopes with no repository selector. Repository write access reaches repositories granted to that
forge identity by its teams; the gate must restrict use to the repository certified for the task. A token scope alone
does not provide that gate restriction. The pinned server's additional token restriction options remain unverified.

Registry revocation locks the account, ends its sessions and deletes every token of the person's forge users after
recording the applied state. An API failure is reported and the next registry intake retries it. A failed service
revocation leaves the local record locked, so a project sync cannot restore host access. Lock, last-membership removal
and purge retain their all-token revocation paths. Lock and purge remove legacy token delivery directories without
following links.

The collection's gate setup and bring still use their earlier vault and runtime-file credential paths. Their migration
to this API, removal of the identities stop and its Molecule callers, and the Porelo task-start consumer are pending.
The host API alone does not establish the complete task-to-gate workflow or the no-token-file guarantee for bring.
