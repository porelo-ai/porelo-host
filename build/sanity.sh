#!/bin/sh
# Runs ansible-test sanity on the collection in the tools image build/tools-image pins, with sanity's requirements
# installed by hash from build/sanity/requirements.txt, and no network while it runs; the same here and in the Build.
# usage: build/sanity.sh [<ansible-test sanity argument>...]
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
image=$(cat "$root/build/tools-image")
# Taken by digest only: a tag alone could be moved to another image under the same name.
printf '%s\n' "$image" | grep -Eqx '[a-z0-9./-]+:[A-Za-z0-9._-]+@sha256:[0-9a-f]{64}' \
    || { echo "REFUSED: build/tools-image names no image by digest: $image" >&2; exit 1; }
command -v podman >/dev/null || { echo "REFUSED: podman is not installed, and it runs the sanity" >&2; exit 1; }
podman build -q --pull=missing --build-arg "TOOLS_IMAGE=$image" -t localhost/porelo-host-sanity "$root/build/sanity" \
    >/dev/null
# ansible-test takes the collection as a copy of the files git holds or would add, so nothing is written to the checkout
# and a worktree is read as a clone is. An empty or failed list stops the run rather than checking nothing.
list=$(mktemp)
trap 'rm -f "$list"' EXIT
GIT_CONFIG_GLOBAL=/dev/null git -C "$root" ls-files -z --cached --others --exclude-standard > "$list"
[ -s "$list" ] || { echo "REFUSED: git names no file of $root to check" >&2; exit 1; }
# Its pip bootstrap script is looked for in the home's cache, and each test's virtual environment is made there.
tar -C "$root" --null -T "$list" -cf - \
    | podman run --rm -i --network none --userns=keep-id --user "$(id -u):$(id -g)" -e HOME=/tmp \
        -e PYTHONDONTWRITEBYTECODE=1 localhost/porelo-host-sanity sh -c '
            set -eu
            work=/tmp/work/ansible_collections/porelo/host
            mkdir -p "$work" "$HOME/.ansible/test/cache"
            tar -C "$work" -xf -
            cp /opt/sanity/get_pip_25_2.py "$HOME/.ansible/test/cache/"
            cd "$work"
            exec ansible-test sanity --local --python 3.14 --color no "$@"' sanity "$@"
