# HO96 — The Registry Named The Organization On The Host

**Status:** Implementing.
**Size:** M - the person helper's verbs and files, the sudoers line, the interface's status answer, the documents and
tests; a hard cut with no transition.

**What must be true.** The host speaks of its organization, never of a registry: its verbs, files, answers and
documents use the name, and nothing reads the old ones.

## Plan

- `roles/porelo/files/porelo-host-person`: `registry …` becomes `org …` (`org status`, `org pin`), its files move from
  `/etc/porelo-host/registry/` to `/etc/porelo-host/organization/`, and the JSON answer names `organization` where it
  named `registry`; `porelo-host-person.sudoers` follows.
- Only Porelo's registry is renamed: the forge's package registry (`publisher.yml`, `MAVEN_SNAPSHOTS_URL`, the
  container registry) keeps its name.
- `doc/ssh.md`, `doc/task-certificates.md`, `doc/local-forge.md`, the roles' READMEs and the changelog follow.
- Red first: the old verb and the old directory are refused, not read.

## Acceptance

- A search for "registry" in the collection finds only the forge's package registry and the changelog's history.
- The unit suite and Molecule pass under the new names.
