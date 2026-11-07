#!/bin/sh
# The check of an agent's move, read-only, run on the host in the account of the person who started the task. Each line
# says what it found and fails by name, so it is red before a trial and green after. It posts nothing: whoever posted
# the waking message in the room says they read its answer there, with --wake-answered.
# Each line reads its fact where it is held. The push: the head on the host's forge of the task's branch from
# `porelo task status`, or the next free one the gate's approve takes
# (<branch>-2, -3, ...), read through the forge's git port with the person's vault answering Git's credential protocol,
# so no token is on a command line and none is made anew. The Build: `porelo build status` for that branch, "not
# configured" without a builds: block. The conversation: a message the task sent that the matrix transport took, from
# `porelo talk log`. The pull request: the forge's open requests for that head and the repository's default branch.
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
conf=${PORELO_HOST_FORGE_CONF:-/etc/porelo-host/forge.conf}
port=$(sed -n 's/^git_port=//p' "$conf" 2>/dev/null | head -n 1)
forge=$(sed -n 's/^name=//p' "$conf" 2>/dev/null | head -n 1)
one_line() { # <value> <extended regular expression the whole of it matches>, refusing a second line
    case $1 in *'
'*) return 1 ;; esac
    printf '%s\n' "$1" | grep -Eqx "$2"
}

held=
pushed=
default=
why=
# What is asked of porelo and the forge below is named by these alone, each read and held to its form once.
named=0
if one_line "$branch" '[A-Za-z0-9][A-Za-z0-9._/-]*' \
    && one_line "$project/$repository" '[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*'; then
    named=1
fi
if [ "$named" != 1 ]; then
    why="porelo task status names no forge branch and repository"
elif ! one_line "$port" '[1-9][0-9]{0,4}' || ! one_line "$forge" '[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?'; then
    why="$conf names no valid git_port and name"
else
    base=http://127.0.0.1:$port
    # The person's vault answers Git for this one address; the token reaches Git on a pipe alone.
    # Nothing of the person's or the system's Git configuration takes part, a redirect included.
    if heads=$(GIT_TERMINAL_PROMPT=0 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null git \
        -c "credential.$base.helper=!porelo vault credential --entry $forge.person" \
        -c protocol.allow=never -c protocol.http.allow=always -c http.proxy= -c http.followRedirects=false \
        ls-remote --symref "$base/$project/$repository.git" HEAD 'refs/heads/*' 2>/dev/null); then
        # The gate's latest forward of the push: the branch itself counts as 1, <branch>-<n> as n.
        held=$(printf '%s\n' "$heads" | awk -v branch="refs/heads/$branch" '
            $1 !~ /^[0-9a-f]+$/ || (length($1) != 40 && length($1) != 64) { next }
            $2 == branch { n = 1 }
            $2 != branch {
                if (index($2, branch "-") != 1 || substr($2, length(branch) + 2) !~ /^[0-9]+$/) next
                n = substr($2, length(branch) + 2) + 0
            }
            n > best { best = n; found = $2 }
            END { if (found != "") { sub(/^refs\/heads\//, "", found); print found } }')
        pushed=$(printf '%s\n' "$heads" | awk -v branch="refs/heads/$held" '$2 == branch { print $1; exit }')
        default=$(printf '%s\n' "$heads" | awk '$1 == "ref:" && $3 == "HEAD" && $2 ~ /^refs\/heads\// {
            sub(/^refs\/heads\//, "", $2); print $2; exit }')
    else
        why="the host's forge answered no branches of $project/$repository"
    fi
fi
if [ -n "$held" ]; then
    line 0 "its last push $pushed reached the forge as $held"
elif [ -n "$why" ]; then
    line 1 "its last push reached the forge: cannot say: $why"
else
    line 1 "its last push reached the forge as $branch or $branch-<n>: no branch head found"
fi

build=
asked=1
if [ "$named" = 1 ]; then
    build=$(porelo build status -p "$project" -r "$repository" "--branch=${held:-$branch}" --logs=none --json \
        2>/dev/null)
    asked=$?
fi
# 78 is the build reader's answer for a project without a builds: block, and only for that.
found=1
verdict="reader failed (exit $asked)"
if [ "$asked" -eq 78 ]; then
    verdict="not configured: the project has no builds:"
    found=0
elif [ "$asked" -eq 0 ]; then
    verdict=$(printf '%s' "$build" | field verdict)
    case $verdict in success | failure | running | queued | cancelled) found=0 ;; esac
    # A Build of an earlier commit, or of a branch the push never reached, is not one of that push.
    read_commit=$(printf '%s' "$build" | field commit)
    if [ "$found" = 0 ] && { [ -z "$pushed" ] || [ "$read_commit" != "$pushed" ]; }; then
        verdict="of ${read_commit:-no commit}, not of the push ${pushed:-that was not found}"
        found=1
    fi
fi
line "$found" "a Build of that push was read by the forge's build reader: ${verdict:-nothing}"

pulls() {
    # The credential protocol and curl config keep the person's existing token off every command line.
    credential=$(printf 'protocol=http\nhost=127.0.0.1:%s\n\n' "$port" \
        | porelo vault credential --entry "$forge.person" 2>/dev/null) || return 1
    config=$(printf '%s\n' "$credential" | python3 -Ic 'import re,sys
passwords = [line.removeprefix("password=") for line in sys.stdin.read().splitlines() if line.startswith("password=")]
if len(passwords) != 1 or not re.fullmatch(r"[A-Za-z0-9+/=_.-]+", passwords[0]):
    sys.exit(1)
print("header = \"Authorization: token " + passwords[0] + "\"")') || return 1
    printf '%s\n' "$config" | curl -q -fsSL --max-redirs 0 --noproxy '*' --proto '=http' \
        --connect-timeout 5 --max-time 30 -K - \
        "$base/api/v1/repos/$project/$repository/pulls?state=open&page=$1" 2>/dev/null
}

found=1
why="no branch head or default branch found on the host's forge"
if [ -n "$held" ] && one_line "$default" '[A-Za-z0-9][A-Za-z0-9._/-]*'; then
    why="no open pull request for $held targeting $default"
    page=1
    while :; do
        if ! requests=$(pulls "$page"); then
            why="the host's forge pull request reader failed"
            break
        fi
        if ! match=$(printf '%s' "$requests" | python3 -Ic 'import json,sys
requests = json.load(sys.stdin)
if not isinstance(requests, list):
    sys.exit(1)
print("found" if any(p["head"]["ref"] == sys.argv[1] and p["base"]["ref"] == sys.argv[2]
                     for p in requests) else "more" if requests else "end")' "$held" "$default" 2>/dev/null); then
            why="the host's forge answered invalid pull requests"
            break
        fi
        case $match in found) found=0; break ;; end) break ;; esac
        page=$((page + 1))
        # A forge that never answers an empty page must not hold the check.
        if [ "$page" -gt 50 ]; then
            why="the host's forge answered more than 50 pages of open pull requests"
            break
        fi
    done
fi
if [ "$found" -eq 0 ]; then
    line 0 "the pull request was opened by the gate: $held targeting $default"
else
    line 1 "the pull request was opened by the gate: $why"
fi

porelo talk log "$task" 2>/dev/null | awk '$2 == "sent" && $NF == "matrix" { joined = 1 } END { exit !joined }'
line $? "the task joined the project's conversation: the matrix transport took a message it sent"

found=1
[ "$answered" != --wake-answered ] || found=0
line "$found" "a message naming $agent wakes it, and its answer appears there: said by whoever posted it"

exit "$wrong"
