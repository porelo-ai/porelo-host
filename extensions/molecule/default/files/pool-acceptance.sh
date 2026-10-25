#!/bin/sh
# Runs as the acceptance leg's unprivileged account, with no model or provider credential.
set -eu
[ "$(id -un)" = acceptance ] || { echo 'expected acceptance account' >&2; exit 1; }
[ "$(cat /var/lib/porelo-pool/run)" = ready ] || { echo 'pool account is not ready' >&2; exit 1; }
for path in /home/run/left-by-pool-acceptance /etc/left-by-pool-acceptance; do
    [ ! -e "$path" ] || { echo "earlier run left $path" >&2; exit 1; }
done
porelo --help
printf 'a leg\n' > "$HOME/left-by-pool-leg"
echo 'pool acceptance leg passed'
