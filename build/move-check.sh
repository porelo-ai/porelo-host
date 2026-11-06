#!/bin/sh
# The check of an agent's move, read-only, run on the host in the account of the person who started the task. Each line
# says what it found and fails by name, so it is red before a trial and green after. It posts nothing: whoever posted
# the waking message in the room says they read its answer there, with --wake-answered.
# Each line reads its fact where it is held. The push: the task's forge branch and newest pushed commit from
# `porelo task status`, found on the host's forge as that branch or the next free one the gate's approve takes
# (<branch>-2, -3, ...), read through the forge's git port with the person's vault answering Git's credential protocol,
# so no token is on a command line and none is made anew. The Build: `porelo build status` for that branch, "not
# configured" without a builds: block. The conversation: a message the task sent that the matrix transport took, from
# `porelo talk log`.
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

text=$(porelo task status "$task" 2>/dev/null)
branch=$(printf '%s\n' "$text" | awk '$1 == "forge" { print $2; exit }')
pushed=$(printf '%s\n' "$text" | awk '$1 == "build" { print $2; exit }')
conf=${PORELO_HOST_FORGE_CONF:-/etc/porelo-host/forge.conf}
port=$(sed -n 's/^git_port=//p' "$conf" 2>/dev/null | head -n 1)
forge=$(sed -n 's/^name=//p' "$conf" 2>/dev/null | head -n 1)
held=
why=
if ! printf '%s' "$branch" | grep -Eqx '[A-Za-z0-9][A-Za-z0-9._/-]*'; then
    why="porelo task status names no forge branch"
elif [ -z "$pushed" ]; then
    why="porelo task status names no pushed commit, which it shows only with a builds: block"
elif ! printf '%s' "$pushed" | grep -Eqx '[0-9a-f]{7,64}'; then
    why="porelo task status names no commit but '$pushed'"
elif ! printf '%s' "$port" | grep -Eqx '[1-9][0-9]{0,4}' \
    || ! printf '%s' "$forge" | grep -Eqx '[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?'; then
    why="$conf names no valid git_port and name"
elif ! printf '%s/%s' "$project" "$repository" | grep -Eqx '[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*'; then
    why="the task names no forge repository"
else
    base=http://127.0.0.1:$port
    # The person's vault answers Git for this one address; the token reaches Git on a pipe alone.
    heads=$(GIT_TERMINAL_PROMPT=0 git -c credential.helper= \
        -c "credential.$base.helper=!porelo vault credential --entry $forge.person" \
        -c protocol.allow=never -c protocol.http.allow=always -c http.proxy= \
        ls-remote --heads "$base/$project/$repository.git" 2>/dev/null) \
        || why="the host's forge answered no branches of $project/$repository"
    held=$(printf '%s\n' "$heads" | awk -v branch="refs/heads/$branch" -v commit="$pushed" '
        index($1, commit) == 1 && ($2 == branch \
            || index($2, branch "-") == 1 && substr($2, length(branch) + 2) ~ /^[0-9]+$/) {
            sub(/^refs\/heads\//, "", $2); print $2; exit
        }')
fi
if [ -n "$held" ]; then
    line 0 "its last push $pushed reached the forge as $held"
elif [ -n "$why" ]; then
    line 1 "its last push reached the forge: cannot say: $why"
else
    line 1 "its last push $pushed reached the forge as $branch or $branch-<n>: neither holds it"
fi

build=
asked=1
if [ -n "$project" ] && [ -n "${held:-$branch}" ]; then
    build=$(porelo build status -p "$project" -r "$repository" "--branch=${held:-$branch}" --logs=none --json \
        2>/dev/null)
    asked=$?
fi
verdict=$(printf '%s' "$build" | field verdict)
# 78 is the build reader's answer for a project without a builds: block, and only for that.
[ "$asked" -ne 78 ] || verdict="not configured"
case $verdict in success | failure | running | queued | cancelled) found=0 ;; *) found=1 ;; esac
line "$found" "a Build of that push was read by the forge's build reader: ${verdict:-nothing}"

printf '%s\n' "$text" | grep -Eq '^pull req +https?://'
line $? "the pull request was opened by the gate"

porelo talk log "$task" 2>/dev/null | awk '$2 == "sent" && $NF == "matrix" { joined = 1 } END { exit !joined }'
line $? "the task joined the project's conversation: the matrix transport took a message it sent"

found=1
[ "$answered" != --wake-answered ] || found=0
line "$found" "a message naming $agent wakes it, and its answer appears there: said by whoever posted it"

exit "$wrong"
