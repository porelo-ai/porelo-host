# The local forge

The local forge is the host's private Forgejo: it holds task branches, runs independent builds and supplies snapshots
through its local registry. The central forge holds the work the person sends outward and runs the central publication
workflows. These are separate destinations, with separate credentials.

![Task branches are built on the local forge, merged by the person, and sent to the central forge by a gathered push; central changes return through central/main](images/local-forge.svg)

A traffic cone marks a step not built yet.

This arrangement uses a project whose security class is `online` and whose repositories name the local forge as their
immediate Git destination. The literal project-file key is `upstream`: here it means the local forge, even though the
central forge is the destination of the gathered push. See Porelo's [project
file](https://github.com/porelo-ai/porelo/blob/main/doc/project-file.md) for the schema and [security
boundary](https://github.com/porelo-ai/porelo/blob/main/doc/security.md) for what the gate permits when the task pushes.

## Task branches and the local build

An `online` task pushes through its gate to `porelo/<task>` on the local forge immediately. The host lends the Git
credential; the task holds no credential for that Git destination. A refusal by the local forge fails the task's push.
The branch is where the person can review the work in a pull request.

The local build runs on the forge's runner, independently of checks the agent runs inside the task. The repository's
workflow determines its triggers and checks. A repository's workflow must run on task-branch pushes or pull requests
before there is a local build to review.

The forge is off by default. The host setting `porelo_host_forge: true` turns on Forgejo, its registry and its runner.
Forgejo Actions is enabled by the role. The forge and runner use separate system accounts and rootless containers, apart
from Porelo's account. Their resource bounds are in the [host lifecycle](index.md).

A VM pool is optional. Defining `porelo_host_vm_pool` turns it on, with `systems` chosen from `ubuntu` and `fedora`, and
`accounts` from 1 to 8 for each system. It requires the forge and gives each run account a VM of its own. Without that
setting, no pool is made; a runner job does not need a VM unless its workflow asks for one.

Where the pool exists, jobs receive its description read-only at `/etc/porelo-host/pool/pool.json` and its run key as
the Actions secret `PORELO_POOL_SSH`. The pool supports `porelo-machines acceptance --pool`. Giving a VM back powers it
off; the host reverts its base snapshot so a run's changes do not reach the next run. See the [pool
role](https://github.com/porelo-ai/porelo-host/blob/main/roles/vm_pool/README.md) for its contract.

Porelo reads build verdicts and failed-job logs through the `forgejo` build reader on the host, outside every task, and
delivers them into the task's `/porelo/files`. The reader receives its credential from the vault for each call. This is
independent of any task access to declared services. Install and configure the reader as described in the [adapter
documentation](https://github.com/porelo-ai/porelo-adapters/blob/main/doc/index.md#forgejo-actions) and Porelo's
[build-reader contract](https://github.com/porelo-ai/porelo/blob/main/doc/build-readers.md).

## The local registry and publication settings

The local registry lets repositories resolve each other's snapshots without first publishing them outward. With
repositories configured, `up` creates a package-only publisher account, supplies its token as an organization Actions
secret and sets the local Actions variables below. The central values are what the central forge's workflows read; `up`
sets the local forge's values only.

| Variable or secret | Local forge, set by `up` | Central forge configuration |
|---|---|---|
| `vars.PORELO_PUBLISH` | `false` | `true` |
| `vars.PORELO_DEPLOY_PROFILE` | `forge-release` | `central-sonatype-release` |
| `vars.MAVEN_SNAPSHOTS_URL` | `https://<forge_address>:<forge_http_port>/api/packages/<forge_owner>/maven` | `https://central.sonatype.com/repository/maven-snapshots/` |
| `secrets.PORELO_PUBLISHER_TOKEN` | The local publisher's package token; private registry reads need authentication too | A placeholder for anonymous Sonatype snapshot reads; central deployment uses its own credentials |

The local address uses the VPN address and port reached by a runner job; the default port is `3000` and the default
organization is `porelo`. The forge's browser address is `https://forge.porelo.internal/`. Jobs trust the host's CA
through the runner's certificate bundle and JVM trust store.

Two differences from GitHub reach a job. The JVM trust store comes through `JAVA_TOOL_OPTIONS`, so every JVM a job
starts announces it on stderr; a test that reads a child JVM's stderr together with its output must keep them apart.
The organization and its repositories are private, so a step that fetches again after a checkout without credentials
fails, where GitHub's public repository needs none.

**`PORELO_PUBLISH=false` still deploys snapshots to the forge's registry** when the workflow's deploy conditions hold.
`PORELO_DEPLOY_PROFILE` selects that destination. For example, the buildtools workflow deploys on `main` pushes and
version tags; its deployment job is not switched off by `PORELO_PUBLISH`. Registry credentials also allow a workflow to
publish a task branch's snapshot, but do not make every task-branch push deploy one.

`PORELO_PUBLISH=false` skips the outward publication and central-only jobs that workflows guard with that variable, such
as Artifactory uploads and deleting central workflow runs. In buildtools it also skips rebuilding the machine snapshots
used by the machine provider. It does not disable the local build or every artifact upload. The same variable names on
both forges let workflows select their destinations without editing the workflow between them.

## The person's two decisions

**First, accept the work by merging `porelo/<task>` into local `main`.** The person reads the pull request and its local
build before merging in Forgejo. This arrangement requires protected local `main`, so direct pushes cannot substitute
for that decision. Automatic setup of this protection is not built: the forge role migrates repositories without
configuring branch protection. Configure protection before relying on this acceptance boundary.

The blue arrows in the picture place forge observation on the host. Build reading works; the additional review and
lifecycle steps are not built:

- Start a reviewer after a green build: not built yet.
- Run a task in the reviewer role: not built yet.
- Read pull-request comments, send replies and wake the developer task: not built yet.
- End the task after the person merges its pull request: not built yet.

**Second, start a gathered push of accepted local `main` to the central forge.** This is a separate decision about
sending the merged work outward. The person starts it on the host over SSH, naming the repositories in their order:

    sudo porelo-host-push porelo-message-sluice

It asks once for the central forge's token, without showing it, and keeps it only for the run. For each repository it
reads local `main` with the forge admin's token and pushes it to the repository's migration source with a plain
`git push` without force, the next only once the one before was taken. A repository the forge does not hold is refused
before anything is read. `/etc/porelo-host/forge/push.conf`, root's, names the repositories, their central
addresses and the authority the central forge is trusted by, `porelo_host_forge_central_ca`, the system's CA bundle by
default; the host's own CA is never trusted for it. `up` writes the file where repositories are configured, and
`down` removes it with the command.

When central `main` holds commits local `main` lacks, the push is refused and nothing is lost on either forge. The
command names those commits and brings central `main` to the local forge as the branch `central/main`, which a task
merges into the local work. That task's branch receives a local build and the person's merge decision before the
person runs the push again. The repositories named after a refused one are not pushed, and the command says which.
Starting that merge task automatically is not built.

## Credentials belong to their destination

Each name in `porelo_host_forge_agents` gets its own local forge account, `agent-<name>`, when repositories are
configured. Its team can write the organization's code, pull requests and issues, and read actions and packages; it
cannot create repositories. Its token is written into `/etc/porelo-host/forge/agents/<name>.token`, owned by root, mode
`0600`, in a `0700` directory. An existing file is kept across `up`; removing an inventory name does not delete the
account or token. These accounts carry no authority to write to the central forge.

An agent's push starts the workflows' `push` and `pull_request` runs, but the forge refuses it a `workflow_dispatch`
(`403`), since the team only reads Actions. Its token also reads no job's log (`404` through the API), no push mirror
(`403`) and not its own user (`403`, no `read:user` scope). No person has a password for the forge's web pages, so a
job's log is read from Forgejo's data on the host.

The registry publisher is a separate account. Its package token stays with Forgejo and runner jobs as
`PORELO_PUBLISHER_TOKEN`; it is not handed to tasks. The host build reader's credential and a task's declared service
credentials have their own routes, described in [Porelo's credential
documentation](https://github.com/porelo-ai/porelo/blob/main/doc/credentials.md).

The gathered push asks for the central token with hidden input in the SSH terminal and stores it nowhere; git
receives it only as a header in its environment, never on a command line, and the command's output names no token. The
token for initial repository migration has a different lifetime: the forge role reads it from the person's drive into
the migration request.

## If the host is lost

Work that exists only on the host is lost with it: task branches, accepted local `main` commits not sent centrally,
local build records and local registry snapshots. A green local build or a local merge does not put that work on the
central forge.

`down` removes the forge's volumes and credentials and the pool's VMs, snapshots and keys. It stops tasks but leaves
their containers and workspaces on the host, then clears the vault. The drive role waits for data already written to the
person's synced folder to finish syncing before unlinking and unmounting it. None of these teardown roles exports the
local forge, its registry or task workspaces to that folder. Preserve local-only work before teardown; drive syncing
alone does not preserve it.
