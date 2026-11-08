#!/bin/sh
# The check of an agent's move, read-only, run on the host in the account of the person who started the task. Each line
# says what it found and fails by name, so it is red before a trial and green after. It posts nothing: whoever posted
# the waking message in the room says they read its answer there, with --wake-answered.
# Each line reads its fact where it is held. The push: the head on the host's forge of the task's branch from
# `porelo task status`, or the next free one the gate's approve takes
# (<branch>-2, -3, ...), in the one repository of the project's organization that holds it, since the forge names a
# repository by its central name and the task by its key; read through the forge's git port with the person's vault
# answering Git's credential protocol, so no token is on a command line and none is made anew. The Build: `porelo
# build status` for that branch; the host names builds: for every project on its forge, so "not configured" fails.
# The conversation: a message the task sent that the matrix transport took, from `porelo talk log`. The pull request:
# the forge's open requests for that head and the repository's default branch.
# A failing line says what was answered: the forge's HTTP status and path, Git's fatal line or the vault's refusal.
# usage: build/move-check.sh <task> <agent's name in the room> [--wake-answered]
set -u
[ $# -ge 2 ] || {
    echo "usage: $0 <task> <agent's name> [--wake-answered]" >&2
    exit 64
}
task=$1
agent=$2
newline='
'
# Git's own words when it refuses, which name the address and never the token.
said=$(mktemp) || {
    echo "FAILED: no temporary file for Git's answers" >&2
    exit 1
}
# dash runs no EXIT trap on a signal, so a signal exits through it.
trap 'rm -f "$said"' EXIT
trap 'exit 130' HUP INT TERM
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
holder=
# What is asked of porelo and the forge below is named by these alone, each read and held to its form once.
named=0
if one_line "$branch" '[A-Za-z0-9][A-Za-z0-9._/-]*' \
    && one_line "$project/$repository" '[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*'; then
    named=1
fi

api() { # <path under /api/v1>: the forge's answer when it is 200, else what was answered; the token on curl's config
    credential=$(printf 'protocol=http\nhost=127.0.0.1:%s\n\n' "$port" \
        | porelo vault credential --entry "$forge.person" 2>/dev/null) || {
        echo "the vault gave no token for $forge.person"
        return 1
    }
    config=$(printf '%s\n' "$credential" | python3 -Ic 'import re,sys
passwords = [line.removeprefix("password=") for line in sys.stdin.read().splitlines() if line.startswith("password=")]
if len(passwords) != 1 or not re.fullmatch(r"[A-Za-z0-9+/=_.-]+", passwords[0]):
    sys.exit(1)
print("header = \"Authorization: token " + passwords[0] + "\"")') || {
        echo "the vault gave no token for $forge.person"
        return 1
    }
    answer=$(printf '%s\n' "$config" | curl -q -sS --max-redirs 0 --noproxy '*' --proto '=http' \
        --connect-timeout 5 --max-time 30 -K - -w '\n%{http_code}' "$base/api/v1/$1" 2>/dev/null) || {
        echo "the host's forge gave no answer for ${1%%\?*}"
        return 1
    }
    code=${answer##*"$newline"}
    if [ "$code" != 200 ]; then
        echo "the host's forge answered HTTP $code for ${1%%\?*}"
        return 1
    fi
    printf '%s' "${answer%"$newline"*}"
}

repositories() { # the names of the organization's repositories on the forge, one a line, each held to its form
    page=1
    while :; do
        answer=$(api "orgs/$project/repos?limit=50&page=$page") || {
            printf '%s\n' "$answer"
            return 1
        }
        batch=$(printf '%s' "$answer" | python3 -Ic 'import json,re,sys
rows = json.load(sys.stdin)
if not isinstance(rows, list) or not all(
        isinstance(row, dict) and isinstance(row.get("name"), str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", row["name"]) for row in rows):
    sys.exit(1)
print("\n".join(row["name"] for row in rows))' 2>/dev/null) || return 2
        [ -n "$batch" ] || return 0
        printf '%s\n' "$batch"
        page=$((page + 1))
        [ "$page" -le 50 ] || return 3
    done
}

heads_of() { # <repository>: its HEAD and branches, the person's vault answering Git for this one address
    # Nothing of the person's or the system's Git configuration takes part, a redirect included.
    GIT_TERMINAL_PROMPT=0 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null git \
        -c "credential.$base.helper=!porelo vault credential --entry $forge.person" \
        -c protocol.allow=never -c protocol.http.allow=always -c http.proxy= -c http.followRedirects=false \
        ls-remote --symref "$base/$project/$1.git" HEAD 'refs/heads/*'
}

latest() { # the gate's latest forward of the push in the heads on standard input: the branch counts 1, <branch>-<n> n
    awk -v branch="refs/heads/$branch" '
        $1 !~ /^[0-9a-f]+$/ || (length($1) != 40 && length($1) != 64) { next }
        $2 == branch { n = 1 }
        $2 != branch {
            if (index($2, branch "-") != 1 || substr($2, length(branch) + 2) !~ /^[0-9]+$/) next
            n = substr($2, length(branch) + 2) + 0
        }
        n > best { best = n; found = $2 }
        END { if (found != "") { sub(/^refs\/heads\//, "", found); print found } }'
}

if [ "$named" != 1 ]; then
    why="porelo task status names no forge branch and repository"
elif ! one_line "$port" '[1-9][0-9]{0,4}' || ! one_line "$forge" '[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?'; then
    why="$conf names no valid git_port and name"
else
    base=http://127.0.0.1:$port
    listed=0
    names=$(repositories) || listed=$?
    case $listed in
        0) ;;
        1) why=$(printf '%s\n' "$names" | tail -n 1) ;;
        2) why="the host's forge answered an invalid list of the repositories of $project" ;;
        *) why="the host's forge answered more than 50 pages of repositories of $project" ;;
    esac
    holders=
    if [ "$listed" = 0 ]; then
        for name in $names; do
            if ! answer=$(heads_of "$name" 2>"$said"); then
                why="the host's forge answered no branches of $project/$name: $(grep -m 1 '^fatal:' "$said")"
                holders=
                break
            fi
            forward=$(printf '%s\n' "$answer" | latest)
            if [ -n "$forward" ]; then
                holders="$holders $name"
                holder=$name
                heads=$answer
                held=$forward
            fi
        done
    fi
    if [ -n "$why" ]; then
        held=
    elif [ -z "$holders" ]; then
        why="no repository of $project on the host's forge holds $branch or $branch-<n>"
    elif [ "$holders" != " $holder" ]; then
        why="several repositories of $project hold $branch:$holders"
        held=
    fi
    if [ -n "$held" ]; then
        pushed=$(printf '%s\n' "$heads" | awk -v branch="refs/heads/$held" '$1 ~ /^[0-9a-f]+$/ && $2 == branch {
            print $1; exit }')
        default=$(printf '%s\n' "$heads" | awk '$1 == "ref:" && $3 == "HEAD" && $2 ~ /^refs\/heads\// {
            sub(/^refs\/heads\//, "", $2); print $2; exit }')
    fi
fi
if [ -n "$held" ]; then
    line 0 "its last push $pushed reached the forge as $held in $project/$holder"
else
    case $why in
        "no repository "* | "several repositories "*) line 1 "its last push reached the forge: $why" ;;
        *) line 1 "its last push reached the forge: cannot say: $why" ;;
    esac
fi

build=
asked=1
if [ "$named" = 1 ]; then
    build=$(porelo build status -p "$project" -r "$repository" "--branch=${held:-$branch}" --logs=none --json \
        2>/dev/null)
    asked=$?
fi
# 78 is the build reader's answer for a project without a builds: block, which a host with a forge never writes.
found=1
verdict="reader failed (exit $asked)"
if [ "$asked" -eq 78 ]; then
    verdict="not configured: the reader sees no builds: for $project"
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

pulls() { # <page>: the forge's open pull requests of the repository that holds the push
    api "repos/$project/$holder/pulls?state=open&page=$1"
}

found=1
why="no branch head or default branch found on the host's forge"
if [ -n "$held" ] && one_line "$default" '[A-Za-z0-9][A-Za-z0-9._/-]*'; then
    why="no open pull request for $held targeting $default"
    page=1
    while :; do
        if ! requests=$(pulls "$page"); then
            why=$requests
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
