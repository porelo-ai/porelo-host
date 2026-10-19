# What a program reads from a run

`host up` and `host down`, porelo-frontend's command, run this collection's playbooks on the host with

    ANSIBLE_STDOUT_CALLBACK=porelo.host.lines ansible-playbook -c local -i <inventory> porelo.host.up

and read the run from its standard output, one JSON object per line, in place of Ansible's text.

**A step's lines.** A task's start, then its end, each naming the play and the task:

    {"v": 1, "play": "<play>", "task": "<task>", "state": "started", "msg": ""}
    {"v": 1, "play": "<play>", "task": "<task>", "state": "ok|changed|skipped|failed", "msg": "<words>"}

A handler's lines are a task's. A meta task, such as `meta: flush_handlers`, writes no line, since Ansible reports no end
for it.

A failure a task ignores ends as `ok`, its `msg` beginning with "failed and ignored". A host Ansible cannot reach ends
the task as `failed`, its `msg` beginning with "unreachable". A task with `no_log` never has its message written:
Ansible hides it before the callback sees it, and the callback writes "hidden, the task has no_log" where it can
tell.

**The stop.** `up`'s second play begins with the step only the person can take. When something is missing it stops
with one line in place of a failure:

    {"v": 1, "state": "waiting", "needs": ["drive", "vault-new"]}

`needs` names what is missing: `drive` when the person's drive is not logged in or not synced, `vault-new` when the
account has no vault yet, `vault` when its vault is shut. `ansible-playbook` itself then exits 2, as on any failure,
so a program tells the stop from a failure by this line, never by the exit code. A second `up` after the person's step
runs both plays from the top; what is done is done, so it goes on where it stopped.

**The version.** `v` is the contract's version. A field that is added keeps it; a field that changes or goes away
raises it.
