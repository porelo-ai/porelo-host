# HO151 — The Pinned-Jdk Action Takes The Shared Rule

```json
{
  "$schema": "issue-1.json",
  "id": "HO151",
  "title": "The Pinned-Jdk Action Takes The Shared Rule",
  "state": "Review",
  "size": "XS",
  "priority": "Medium",
  "rank": 4,
  "blockedBy": [],
  "covers": "The CI's pinned GraalVM is fetched by the shared rule: cached by its digest, tried again by `pinned.sh`, with the job's token from github.com."
}
```

**Why this size.** the steps of `.github/actions/pinned-jdk/action.yml`, `pinned.sh` beside it, and three jobs' time.

**What must be true.** The CI's pinned GraalVM is fetched by porelo-buildtools' shared rule for pinned downloads: kept
by its digest, checked again after a cache hit, tried again by the one rule in `pinned.sh`, and, from
`https://github.com`, with the job's token.

## Why

The action was older than the shared rule. It tried the wrapper's Maven again by a loop of its own, and kept no
GraalVM: every job fetched it from github.com, without the job's token, which is the case the shared rule is for.

## Shape

- `pinned.sh` copied unchanged from porelo-buildtools, so `check-shared` holds it to porelo-buildtools' own.
- The steps are porelo-buildtools' `steps-for-build-pom.yml` as they are: its class path line is this repository's.
  - The digest step names the pinned digest, and says `::error::` when porelo-machines names none.
  - The GraalVM is kept in the cache by that digest; a hit is checked against it again before it is used.
  - The wrapper's Maven is asked again by `pinned_retry`.
  - The install step passes `PORELO_PINNED_GITHUB_TOKEN`, the job's token on github.com alone.
- The three jobs that use the action wait 15 minutes longer: Build's 20 to 35, the shared rules' and the workflows'
  checks 10 to 25.

## Reading

Read once by agy `gemini-4-argon-high` (336 s): no defects. It checked the step ids and outputs inside the composite
action, the token's expression there, the cache paths against `--cache`, that every job using the action has the
longer time and no other uses it, the Maven cache key, that `pinned.sh` stays out of the collection, and that the
class path and `JAVA_HOME` reach the later steps as before.

## Tests

- `check-shared` from the tools' snapshot: `pinned.sh` is the shared one; `check-actions`: every step pinned.
- The digest step, run as the action runs it (`bash -e -o pipefail`): it writes the digest; given a wrong option, it
  says `::error::porelo-machines could not name the pinned digest` and exits 1.
- The install step with an empty cache: the GraalVM fetched, checked against its digest, kept under it, `JAVA_HOME`
  and `PATH` set.
- yamllint, ansible-lint, sanity and the tarball check: `pinned.sh` is not shipped.

## Acceptance

- The first Build on GitHub after the push fetches the GraalVM once, with the job's token, and its log shows no
  token.
- A later Build takes the GraalVM from the cache, checked against its digest.
