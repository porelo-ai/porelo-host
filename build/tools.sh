#!/bin/sh
# Runs one of the Ansible tools from the image build/tools-image pins, on this checkout mounted where ansible-galaxy
# expects a collection, as the account that calls it; the same here and in the Build.
# usage: build/tools.sh <command> [<argument>...]    e.g. build/tools.sh ansible-lint -c build/ansible-lint.yml
set -eu
[ $# -ge 1 ] || { echo "usage: $0 <command> [<argument>...]" >&2; exit 2; }
root=$(cd "$(dirname "$0")/.." && pwd)
image=$(cat "$root/build/tools-image")
# Taken by digest only: a tag alone could be moved to another image under the same name.
printf '%s\n' "$image" | grep -Eqx '[a-z0-9./-]+:[A-Za-z0-9._-]+@sha256:[0-9a-f]{64}' \
    || { echo "REFUSED: build/tools-image names no image by digest: $image" >&2; exit 1; }
command -v podman >/dev/null || { echo "REFUSED: podman is not installed, and it runs the tools" >&2; exit 1; }
work=/work/ansible_collections/porelo/host
# Only this collection's own variables pass in, so nothing else of the caller's environment reaches the tools.
# The checkout is mounted where Ansible finds it as the collection porelo.host, so the playbooks name its roles so.
exec podman run --rm --userns=keep-id --user "$(id -u):$(id -g)" -e HOME=/tmp --env 'PORELO_HOST_*' \
    -e ANSIBLE_COLLECTIONS_PATH=/work -e PYTHONDONTWRITEBYTECODE=1 \
    -v "$root:$work:Z" -w "$work" "$image" "$@"
