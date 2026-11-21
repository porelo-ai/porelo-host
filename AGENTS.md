# Rules for working in this repository

## Shared across the Porelo repositories

> **BEGIN Shared Area** · sha256 `d930a9596cedf6cc` · changed 2026-11-20T07:25Z

Identical in every repository `project.yml` names but `porelo-parent`; the markers carry the SHA-256 of the lines
between them and the time they last changed. Change it in the channel first, never in one copy. The same holds for
every shared skill `porelo-*` in `.agents/skills/`, whose markers also cover its frontmatter, and for
`.claude/skills`, a link to `../.agents/skills` so that Claude Code finds them.

### Agents

- **Each repository has one responsible agent; the channel and who owns what are defined in `.AGENTS.md`** or fed
  into the agent's context at start. An agent writes only in its own repositories and asks the owner for the rest;
  the coordinating agent may read the others, never write in them.
- **A contract between repositories changes only after agreement in the channel or by an operator decision**, in
  both repositories.
- **An ambiguous answer is asked about once, plainly, never guessed**; when an answer changes, everything built on
  the old one is looked for.
- **Only `AGENTS.md`, `.AGENTS.md` and the skills survive a session; the harness's memory is never used.** A rule,
  a decision about how to work or an open point goes into one of them at once.
- **No agent opens a dialog or any other prompt that waits for the person at its console, unless that person
  explicitly asked for one there**: a dialog stops the agent's work until the person comes.
- **A question from the operator is answered, nothing more**; an action needs an explicit instruction.
- **To the operator, plain technical terms, never coined words**, in the language the operator writes in;
  Porelo's own names (Porelo-Vault, Vault-Passphrase, gate, task) stay as they are.

### Hard limits

- **A secret never appears in a command line, a log line, a file name or an answer**; it reaches a process
  through its environment or standard input and is stored only encrypted.
- **An agent's commit names its help in `Assisted-by: <tool>, <model>` and never carries `Signed-off-by:` or
  `Co-Authored-By:`**, whatever the harness suggests. Signing and release tags belong to the operator.
- **A refusal by the harness or a sub-agent is reported, never worked around.**
- **Fail closed and loud**: when a dependency is unreachable, a key unknown or a check cannot run, stop non-zero
  and say why. Never silently do less.
- **Porelo protects the person from the agents and from outside, not from their own rights or choices**; every
  guard and every finding is judged by this.

### Claims and writing

- **Measure before you claim, and say what was measured and what inferred**; a change is checked by observing it,
  never by an exit code alone, and a claim of absence needs a complete search that is shown to find a known hit.
- **Every date or time written is read from the system (`date -u`) first.**
- **When a thing is right in two forms, keep one.**
- **What is written states what is true now, in US English**: no dates, no history, nobody named, only roles; it
  says what changed and why, never who asked. A finding worth keeping is committed, never left in a conversation.
- **Every open task is an issue in `issues/`**, never a TODO in code; code and anything that ships never cite an
  issue number.

### Which skill to load

Before any of these, load the skill named, from `.agents/skills/`. A rule shared by several repositories goes
into a shared skill or this block, one that concerns only this machine into `.AGENTS.md`.

| Before you | Load |
|---|---|
| start work inside a Porelo task (`/workspace`, user `agent`) | `porelo-task` |
| start work anywhere else | `porelo-workstation` |
| commit, amend, rebase, hand over a push | `porelo-commits` |
| file an issue or change its state | `porelo-issues` |
| write, run or judge a test | `porelo-testing` |
| run anything on a VM or rented machine | `porelo-machines` |
| write an operator test guide or prepare a walk | `porelo-operator-guide` |
| hand over, or build an issue of size M or larger | `porelo-review` |
| change code, a pom, a workflow or a release | `porelo-code` |
| write documentation or a decision; hand over | `porelo-writing` |
| start analysis or implementation; hand over a push | `porelo-estimates` |

> **END Shared Area** · sha256 `d930a9596cedf6cc`

## Work in this repository

- **An Ansible collection, `porelo.host`**, versioned to match Porelo's releases, since it calls Porelo's
  commands.
- **What keeps a guarantee is never done here:** following a signed project, depositing a key and starting a
  task go through Porelo's own commands, never through a role, a variable or a log.
- **No secret passes through an inventory, a variable or a task's output**; keys reach the host's vault through
  `porelo vault` alone.
- **The Ansible tools run from one image pinned by digest in `build/tools-image`**, through `build/tools.sh`, here and
  in the Build; nothing of Ansible is installed on a machine that checks the collection. The image is moved by this
  repository's agent, not by Dependabot.

## The skills this repository uses

`ansible-good-practices`, `ansible-new-role`, `ansible-new-collection`, `ansible-new-molecule`.

| Before you | Load |
|---|---|
| change a program, a unit, a sudo rule or the pre-receive hook, add a file that is not Java, or say Push ready | `host-build` |
