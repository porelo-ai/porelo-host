# HO99 — A Central Forge On A Private Authority

**Status:** Idea.

**What must be true.** A central forge whose certificate a private authority signed is reachable by everything on the
host that talks to it, from one setting: the follow's `org fetch`, the read key's calls, the migration and the gathered
push. Today only the push has a setting, `porelo_host_forge_central_ca`.

**Plan.** One host setting names the authority's file. The role adds it to the system bundle, which the read key's calls
use; to the bundle the forge's container mounts, for the migration; and to a configuration directory the fetch's isolated
unit can read, where Porelo looks for `ca-certificates.pem`. The push's setting goes into it. Local networks stay a choice
of their own, `forge_migrations_allow_local`. A test on a VM against such a forge holds each of the four. A public
forge changes nothing.
