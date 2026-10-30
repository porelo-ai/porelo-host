# HO61 — A Purged Person's Matrix Account Taken Off

**Status:** Idea.

**What must be true.** When `porelo-host-person purge` removes a person, their account on the host's own Matrix
homeserver goes too, or the purge names it as left. Today it may stay without a word.

## Why

purge clears the person's vault with `--force`. Where the Matrix transport refuses to clear the account it keeps for
a project, Porelo lists that account as not removed and still clears the vault, and purge accepts it as only a
transport's account kept elsewhere. On a host the transport's server is often the host's own homeserver. `userdel
--remove` takes the person's home but not that account, and only `down` takes it along, with the disk. Until then a
removed person keeps an account on the homeserver that nobody can use and nobody is told about.

## To be checked

- Whether root may deactivate an account on the host's homeserver through its admin interface, and by which name a
  purged person's account is found.
- Whether purge then deactivates it, or only names it in its answer for the host admin.
