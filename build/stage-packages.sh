#!/bin/sh
# Stage one checked local package set before a VM or a remote host is changed.
set -eu
fail() { printf 'FAILED: %s\n' "$*" >&2; exit 1; }
valid() {
    case $1 in *'
'*) return 1 ;; esac
    printf '%s\n' "$1" | grep -Eqx "$2"
}
[ "$#" = 1 ] || fail 'usage: stage-packages.sh <new directory>'
dest=$1
host=${PORELO_HOST_DEB:-}
[ -n "$host" ] && [ -f "$host" ] && [ -r "$host" ] \
    || fail 'PORELO_HOST_DEB must name a readable local porelo-host .deb'
command -v dpkg-deb >/dev/null || fail 'dpkg-deb is required to read PORELO_HOST_DEB'
package=$(dpkg-deb --field "$host" Package) || fail 'cannot read Package from PORELO_HOST_DEB'
[ "$package" = porelo-host ] || fail "PORELO_HOST_DEB contains $package, expected porelo-host"
version=$(dpkg-deb --field "$host" Version) || fail 'cannot read Version from PORELO_HOST_DEB'
valid "$version" '[0-9][A-Za-z0-9.+:~-]*' || fail 'PORELO_HOST_DEB has an invalid Version'
[ ! -e "$dest" ] && [ ! -L "$dest" ] || fail "staging directory already exists: $dest"
mkdir -m 700 -- "$dest"
finish() {
    status=$?
    trap - EXIT HUP INT TERM
    if [ "$status" != 0 ]; then rm -rf -- "$dest"; fi
    exit "$status"
}
trap finish EXIT
trap 'exit 130' HUP INT TERM
cp -- "$host" "$dest/porelo-host.deb"
printf '%s\n' "$version" > "$dest/porelo-host.version"
if [ -n "${PORELO_HOST_PACKAGES:-}" ]; then
    set -- "$PORELO_HOST_PACKAGES"/*.deb
    [ -f "$1" ] || fail 'PORELO_HOST_PACKAGES holds no .deb files'
    for source in "$@"; do
        package=$(dpkg-deb --field "$source" Package) || fail "cannot read Package from $source"
        valid "$package" '[a-z0-9][a-z0-9+.-]*' || fail "invalid Package in $source"
        version=$(dpkg-deb --field "$source" Version) || fail "cannot read Version from $source"
        valid "$version" '[0-9][A-Za-z0-9.+:~-]*' || fail "invalid Version in $source"
        if [ -e "$dest/$package.deb" ]; then
            cmp -s "$source" "$dest/$package.deb" || fail "conflicting local artifacts for $package; check PORELO_HOST_DEB"
            continue
        fi
        cp -- "$source" "$dest/$package.deb"
        printf '%s\n' "$version" > "$dest/$package.version"
    done
fi
(cd "$dest" && sha256sum ./*.deb ./*.version > SHA256SUMS && cat SHA256SUMS >&2)
