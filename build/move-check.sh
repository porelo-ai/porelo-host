#!/bin/sh
# The check of an agent's move, read-only, run on the host in the account of the person who started the task. Each line
# says what it found and fails by name, so it is red before a trial and green after. It posts nothing: whoever posted
# the waking message in the room says they read its answer there, with --wake-answered.
# usage: build/move-check.sh <task> <agent's name in the room> [--wake-answered]
set -u
[ $# -ge 2 ] || {
    echo "usage: $0 <task> <agent's name> [--wake-answered]" >&2
    exit 64
}
task=$1
agent=$2
answered=${3:-}
wrong=0

line() { # <0 when it holds> <what is checked>
    if [ "$1" -eq 0 ]; then
        echo "ok: $2"
    else
        echo "FAILED: $2"
        wrong=1
    fi
}

field() { # <field>, from the JSON on standard input; an absent or null one prints nothing
    python3 -Ic 'import json,sys
try:
    value = json.load(sys.stdin).get(sys.argv[1])
except ValueError:
    value = None
print("" if value is None else str(value).lower() if isinstance(value, bool) else value)' "$1"
}

status=$(porelo task status "$task" --json 2>/dev/null)
project=$(printf '%s' "$status" | field project)
repository=$(printf '%s' "$status" | field repository)
found=1
[ "$(printf '%s' "$status" | field running)" != true ] || found=0
line "$found" "the task runs: $task"

branch=porelo/$task
build=
[ -z "$project" ] || build=$(porelo build status -p "$project" -r "$repository" "--branch=$branch" --logs=none --json 2>/dev/null)
found=1
[ -z "$(printf '%s' "$build" | field commit)" ] || found=0
line "$found" "its last push reached the forge as $branch"

verdict=$(printf '%s' "$build" | field verdict)
case $verdict in success | failure | running | queued | cancelled) found=0 ;; *) found=1 ;; esac
line "$found" "a Build of that push was read by the forge's build reader: ${verdict:-nothing}"

porelo task status "$task" 2>/dev/null | grep -Eq '^pull req +https?://'
line $? "the pull request was opened by the gate"

found=1
[ -z "$project" ] || porelo talk peers "--project=$project" 2>/dev/null | grep -Fxq "$agent" && found=0
line "$found" "the task is listed in the room's agent-card.json as $agent"

found=1
[ "$answered" != --wake-answered ] || found=0
line "$found" "a message naming the agent wakes it, and its answer appears there: said by whoever posted it"

exit "$wrong"
