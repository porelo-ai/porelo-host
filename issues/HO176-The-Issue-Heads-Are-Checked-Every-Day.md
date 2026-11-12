# HO176 — The Issue Heads Are Checked Every Day

```json
{
  "$schema": "issue-1.json",
  "id": "HO176",
  "title": "The Issue Heads Are Checked Every Day",
  "state": "Review",
  "size": "XS",
  "priority": "Low",
  "rank": 100,
  "blockedBy": [],
  "covers": "porelo-host's shared-rules check runs `issues check issues` every day on the checked-out commit, from the released porelo-release, as porelo-buildtools' own does since BT81."
}
```

**Why this size.** one step in `.github/workflows/shared-rules.yml`, beside the citations check.

**What must be true.** The daily shared-rules check refuses an issue head that issue-1.json refuses, or an index that
its heads do not give, naming the file and the field, on the checked-out commit and never on a working tree.

**Why.** Heads on `main` without a size or with a rank of `null` were refused by the planner's board, and nothing refused
them before the push. porelo-buildtools added the step under
[BT81](https://github.com/porelo-ai/porelo-buildtools/blob/main/issues/README.md#bt81); every repository with
`issues/` adds the same one. The work waits until this lane's other issues are through.

## Acceptance

- `shared-rules.yml` runs `porelo-release issues check issues` from the tools it already takes for `check-citations`.
- A run on `main` is green.

## As built

- `shared-rules.yml` runs `issues check issues` after the citations check, from the tools the pinned-jdk action
  already puts on its class path (porelo-buildtools' snapshot from `build/pom.xml`).
- Run locally with those tools: this repository's issues pass, exit 0; a copy whose head has `"rank": null` is refused
  naming the file and `/rank`, exit 1.
