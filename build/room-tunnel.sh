#!/bin/sh
# Lets a person's tasks on a host reach the project's room on this machine while agents move: one remote Unix socket in
# the person's own directory, mode 0600 by ssh's default, to this machine's homeserver port, which nothing else on the
# host can open. It is not the window's return.sock. It prints the homeserver value for the host, then keeps the tunnel
# open, and stops only when killed: a task's transport answers 75 while it is down.
# usage: build/room-tunnel.sh <login on the host> <host> <the homeserver's loopback port>
set -u
usage() {
    echo "usage: $0 <login> <host> <port>: $1" >&2
    exit 64
}
[ $# -eq 3 ] || usage "three arguments"
login=$1
host=$2
port=$3
# grep answers for each line, so a value with a second line would pass on its first.
fits() {
    case $2 in *'
'*) return 1 ;; esac
    printf '%s\n' "$2" | grep -Eqx "$1"
}
fits '[a-z][a-z0-9-]{0,31}' "$login" || usage "no login: $login"
fits '[A-Za-z0-9][A-Za-z0-9.:-]*' "$host" || usage "no host: $host"
fits '[0-9]{1,5}' "$port" && [ "$port" -ge 1 ] && [ "$port" -le 65535 ] || usage "no port: $port"
socket=/run/porelo-host/people/$login/room.sock
echo "unix:$socket"
while :; do
    ssh -N -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
        -o StreamLocalBindUnlink=yes -o ForwardAgent=no -R "$socket:127.0.0.1:$port" "$login@$host"
    [ -z "${ROOM_TUNNEL_ONCE:-}" ] || exit 0
    echo "the tunnel to $host ended; again in 10 seconds" >&2
    sleep 10
done
