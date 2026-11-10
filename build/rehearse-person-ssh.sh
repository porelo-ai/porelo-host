#!/bin/sh
# Runs one command on the rehearsal's host as the test person, for a step under build/rehearse-steps: through the
# person's agent alone and the host key pinned at the run's first connection. Each argument is quoted for the remote
# shell; standard input is forwarded.
set -eu
[ $# -ge 1 ] || { echo "usage: $0 <command> [<argument>...]" >&2; exit 64; }
remote=
for argument do
    quoted=$(printf '%s' "$argument" | sed "s/'/'\\\\''/g")
    remote="$remote '$quoted'"
done
exec ssh -F /dev/null -o BatchMode=yes -o IdentitiesOnly=no -o ConnectTimeout=5 \
    -o IdentityAgent="$REHEARSAL_PERSON_AGENT" -o IdentityFile=none \
    -o UserKnownHostsFile="$REHEARSAL_KNOWN_HOSTS" -o GlobalKnownHostsFile=/dev/null -o StrictHostKeyChecking=yes \
    -o ControlMaster=no -o ControlPath=none -o ClearAllForwardings=yes \
    -- "$REHEARSAL_PERSON@$REHEARSAL_HOST" "$remote"
