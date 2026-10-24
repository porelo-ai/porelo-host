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

    {"v": 1, "state": "waiting", "needs": ["drive", "vault-new"]}

`needs` names what is missing: `drive` when the person has not logged the drive's client in, `vault-new` when the
account has no vault yet, `vault` when its vault is shut. `up` installs agents without stopping for their sign-ins
and starts no task. `ansible-playbook` itself exits 2 on a waiting stop, as on any failure,
so a program tells the stop from a failure by this line, never by the exit code. A second `up` after the person's step
runs both plays from the top; what is done is done, so it goes on where it stopped.

**The version.** `v` is the contract's version. An added field or state keeps it; a field that changes or goes away
raises it. A reader skips a `state` it does not know, as it skips a field.
