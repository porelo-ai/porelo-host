#!/bin/sh
# Refuses a collection tarball that holds anything but what runs and what a person installing it reads, so a file of
# the machine it was built on - .AGENTS.md, an IDE's settings - is never published with it.
# usage: build/check-tarball.sh <porelo-host-*.tar.gz>
set -eu
[ $# -eq 1 ] && [ -r "$1" ] || { echo "usage: $0 <collection tarball>" >&2; exit 2; }
listing=$(tar -tzf "$1")
[ -n "$listing" ] || { echo "REFUSED: $1 lists no file at all" >&2; exit 1; }
outside=$(printf '%s\n' "$listing" | grep -vE '^(MANIFEST\.json|FILES\.json|README\.md|LICENSE|CHANGELOG\.md|(meta|roles|playbooks|plugins)(/.*)?)$' || true)
if [ -n "$outside" ]; then
    echo "REFUSED: $1 holds what the collection must not ship:" >&2
    printf '    %s\n' $outside >&2
    exit 1
fi
hidden=$(printf '%s\n' "$listing" | grep -E '(^|/)\.' || true)
if [ -n "$hidden" ]; then
    echo "REFUSED: $1 holds a dot file, which is a machine's or a tool's, never the collection's:" >&2
    printf '    %s\n' $hidden >&2
    exit 1
fi
for needed in MANIFEST.json FILES.json README.md LICENSE meta/runtime.yml; do
    printf '%s\n' "$listing" | grep -qx "$needed" || { echo "REFUSED: $1 lacks $needed" >&2; exit 1; }
done
echo "OK    $1: $(printf '%s\n' "$listing" | wc -l) entries, each one the collection ships"
