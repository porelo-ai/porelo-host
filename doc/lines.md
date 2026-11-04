# What a program reads from a run

`host up` and `host down`, porelo-frontend's command, run this collection's playbooks on the host with

    ANSIBLE_STDOUT_CALLBACK=porelo.host.lines ansible-playbook -c local -i <inventory> porelo.host.up

and read the run from its standard output, one JSON object per line, in place of Ansible's text.

**A step's lines.** A task's start, then its end, each naming the play and the task:

    {"v": 1, "play": "<play>", "task": "<task>", "state": "started", "msg": ""}
    {"v": 1, "play": "<play>", "task": "<task>", "state": "ok|changed|skipped|failed", "msg": "<words>"}

A handler's lines are a task's. A meta task, such as `meta: flush_handlers`, writes no line, since Ansible reports no end
for it.

A task of the playbook carries its words and usual duration in its own variables:

    vars:
      porelo_host_step:
        text: Installing Porelo
        seconds: 90

Its start adds both fields, read as written, without templating:

    {"v": 1, "play": "<play>", "task": "<task>", "state": "started", "msg": "", "text": "Installing Porelo", "seconds": 90}

`text` is a string. `seconds` is a non-negative integer, never a boolean. Invalid or missing seconds leave the text
alone; invalid or missing text leaves both fields out. A task without its own block, including a role's inner task,
keeps its usual line. A reader tells a step from an inner task by `text` being there; inner tasks belong to the step
before them.

**The run ahead.** Before the first task starts, one line lists every described step of all the playbook's plays,
in play and task order:

    {"v": 1, "state": "plan", "steps": [{"task": "<task>", "text": "Installing Porelo", "seconds": 90}]}

`task` is the name its `started` line carries. The fields follow the same rules as a start. A step under a false
`when` is left out, decided with Ansible's conditions and the run's inventory, play, task and extra variables before
the first task runs. A condition Ansible cannot decide yet leaves the step listed with `"when": true`, such as one
that needs a value a later task supplies. A playbook without described steps gives no plan line. If every described
step is left out, `steps` is empty. `up`'s two plays share one plan, including the steps after the person's stop. A
resumed `up` runs from the top and ends what is done quickly, so the total duration is an upper bound.

A failed step's `msg` carries, after Ansible's words, the command's own words (stderr, else stdout), and for a loop
each failed item's by its label. Each command's words are cut to their last 1000 characters, with a leading "…"
when cut. Each loop entry, label and words together, is at most 1000 characters; long labels are shortened and
words retain their tail with a leading "…". The whole `msg` is at most 4000 characters: a single result keeps the
command's words and shortens Ansible's message to the space left; a loop counts any omitted items. `no_log` hides
as before.

A failure a task ignores ends as `ok`, its `msg` beginning with "failed and ignored". A host Ansible cannot reach ends
the task as `failed`, its `msg` beginning with "unreachable". A task with `no_log` never has its message written:
Ansible hides it before the callback sees it, and the callback writes "hidden, the task has no_log" where it can
tell.

**The stop.** `up`'s second play begins with the step only the person can take. When something is missing it stops
with one line in place of a failure:

    {"v": 1, "state": "waiting", "needs": ["vault-new", "keys"]}

`needs` names what is missing: `vault-new` with `keys` when the account has no vault yet, `vault` when its vault is
shut. `up` starts no task. `ansible-playbook` itself exits 2 on a waiting stop, as on any failure, so a program
tells the stop from a failure by this line, never by the exit code. A second `up` after the person's step runs both
plays from the top; what is done is done, so it goes on where it stopped.

Any other answer about the vault is a failure with words.

A person at the host's terminal may instead run `porelo-host-stop NEED...` as the account, with `vault-new` or
`vault`: `vault-new` asks for a new vault passphrase twice, `vault` for the existing one to unlock it. A failed attempt
shows the command's error and asks `Try again? [Y/n]`. `drive` is no need any more and is refused with 64.

The command exits 0 when every named need is done, 75 on `n`, `N` or Ctrl+C, 64 for a wrong call, and 69 when a
required command is missing. Its last line on success is "The host's stop is done; close this terminal, and setup
goes on." On cancellation it is "Cancelled; the host waits at this stop. Running up again comes back here."

Push and pull run in the person's own account: `/usr/local/sbin/porelo-host-push [--pull] <project> [repos...]`;
root running them is refused with 77. They read the central token on
stdin and only the caller's private push config, and get the local token through
`sudo -n /usr/local/sbin/porelo-host-person forge-token`, which refuses a locked person or one no project holds. That
token replaces the person's last one, so it goes on a pipe into their vault as `<forge>.person`; a vault that takes
none is said on stderr and the push goes on. Local Git reaches the forge on `127.0.0.1:<git_port>`, the same token-only gate `git.sock` is; API requests use the
socket directly. No local CA or vault token is used. Neither push nor pull stores the central token.

**The stop on standard input.** Every need is given from the person's secrets file by one pipeline, as the person:

    <secrets> | ssh <person>@<host> porelo-host-stop --stdin NEED...

with the needs as `up` names them. Standard input holds one line per secret, `<need> <value>` or, for a key,
`key <name> <value>`, the value in base64:

| Need | Its lines | Where the value goes |
|---|---|---|
| `vault-new` | `vault-new <passphrase>` | `porelo vault init --passphrase-stdin`, as the account |
| `vault` | `vault <passphrase>` | `porelo vault unlock --passphrase-stdin`, as the account |
| `keys` | `key <name> <key>`, one per key of the machine, none or more | `porelo vault put <name>`, as the account, once the vault is open |

Every line is checked before any is used: a need not named, an unknown need, a line given twice, a key name other than
letters, digits, `.`, `_` and `-`, or a value that is not base64 is refused, naming the line and never the value, and so
is a named need no line gives; only `keys` beside `vault-new` may come with no line, for a machine without keys. `drive`
is refused, as is a call made as root. The values then go in the table's order, each decoded on a pipe into its
user, and nothing is asked. A key the vault lacks later is given by another call with `keys`;
`up` fails with a message beginning `keys:` for a missing key. Matrix access uses
the transport's Unix socket gate and asks for no machine or registration token at the stop.

It exits 0 when every line is used, printing "Your stop is done."; 64 for a wrong call or a wrong line, with nothing
used; 65 when the vault refuses a value (`vault-new`, `vault`, a key), naming it; and 69 when a required command is missing.

**The version.** `v` is the contract's version. An added field or state keeps it; a field that changes or goes away
raises it. A reader skips a `state` it does not know, as it skips a field.

## The check before an installation

`roles/check/files/porelo-host-check` answers one JSON object on standard output, with no lines:

    {"v": 1, "ok": <bool>, "complete": <bool>, "findings": [
        {"id": "<stable>", "state": "pass|fail|warn|unknown", "found": <value>, "unit": "<unit or null>",
         "asked": <value>, "do": "<words, empty on a pass>"}]}

`complete` says whether the check ran to its end. **`unknown` is what could not be known here, and no one reads it as passed.** Exit 0
when nothing fails and it ran to its end, 1 otherwise; 2 when it could not run at all, with `findings` empty. `up`'s first task runs
the same code and stops with every `fail`, in one line of the usual kind. A login that cannot run it, or a root still closed by an
image's `command=` line, is the interface's own to tell from the login's exit and output.

