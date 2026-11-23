#!/bin/sh
# Runs one command as root on the rehearsal's host, for a step under build/rehearse-steps: through the person's agent
# alone, whose key the run put among root's keys, and the host key pinned at the run's first connection. env -i drops
# the SSH session's variables, which the host program refuses. Each argument is quoted for the remote shell; standard
# input is forwarded.
set -eu
[ $# -ge 1 ] || { echo "usage: $0 <command> [<argument>...]" >&2; exit 64; }
# The remote shell expands its own PATH.
# shellcheck disable=SC2016
remote='exec env -i PATH="$PATH"'
for argument do
    quoted=$(printf '%s' "$argument" | sed "s/'/'\\\\''/g")
    remote="$remote '$quoted'"
done
exec ssh -F /dev/null -o BatchMode=yes -o IdentitiesOnly=no -o ConnectTimeout=5 \
    -o IdentityAgent="$REHEARSAL_PERSON_AGENT" -o IdentityFile=none \
    -o UserKnownHostsFile="$REHEARSAL_KNOWN_HOSTS" -o GlobalKnownHostsFile=/dev/null -o StrictHostKeyChecking=yes \
    -o ControlMaster=no -o ControlPath=none -o ClearAllForwardings=yes \
    -- "root@$REHEARSAL_HOST" "$remote"
