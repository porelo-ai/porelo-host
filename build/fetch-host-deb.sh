#!/bin/sh
# Fetches the porelo-host package the role pins, and porelo of the same run, from Porelo's repository, for a Molecule
# run with no local hand-over (GitHub's runner): both come from one porelo build, as a local hand-over does. apt takes
# them only signed by the key with the pinned fingerprint, as a host's up does; nothing of the machine's own apt
# sources or state is read or changed, and no root is needed.
# usage: build/fetch-host-deb.sh <new directory>     prints porelo-host's .deb; PORELO_HOST_DEB takes it and
#                                                    PORELO_HOST_PACKAGES the directory
set -eu
fail() { printf 'FAILED: %s\n' "$*" >&2; exit 1; }
[ "$#" = 1 ] || fail 'usage: fetch-host-deb.sh <new directory>'
dest=$1
root=$(cd "$(dirname "$0")/.." && pwd)
defaults=$root/roles/porelo/defaults/main.yml
pinned() { sed -n "s/^$1: \"\{0,1\}\([^\"]*\)\"\{0,1\}\$/\1/p" "$defaults"; }
version=$(pinned porelo_host_version)
url=$(pinned porelo_repository_url)
key_url=$(pinned porelo_key_url)
fingerprint=$(pinned porelo_key_fingerprint)
[ -n "$version" ] && [ -n "$url" ] && [ -n "$key_url" ] && [ -n "$fingerprint" ] \
    || fail "cannot read the pins in $defaults"
# A published snapshot is in the snapshots distribution, a release in releases.
case $version in *~snapshot.*) distribution=snapshots ;; *) distribution=releases ;; esac
[ ! -e "$dest" ] && [ ! -L "$dest" ] || fail "directory already exists: $dest"
mkdir -m 700 -- "$dest"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
curl -fsSL --proto '=https' -o "$work/key.asc" "$key_url" || fail "cannot fetch Porelo's key from $key_url"
found=$(gpg --batch --with-colons --show-keys "$work/key.asc" | awk -F: '$1 == "fpr" { print $10 }')
[ "$found" = "$fingerprint" ] || fail "the key at $key_url is not the one with the fingerprint $fingerprint"
gpg --batch --dearmor -o "$work/porelo.gpg" "$work/key.asc"
mkdir -p "$work/lists/partial" "$work/cache/archives/partial" "$work/etc/preferences.d" "$work/etc/sources.list.d"
printf 'deb [signed-by=%s arch=amd64] %s %s main\n' "$work/porelo.gpg" "$url" "$distribution" > "$work/etc/sources.list"
: > "$work/status"
set -- -q -o Dir::Etc="$work/etc" -o Dir::State::Lists="$work/lists" -o Dir::State::status="$work/status" \
    -o Dir::Cache="$work/cache" -o Debug::NoLocking=1 -o APT::Sandbox::User="$(id -un)"
apt-get "$@" update >&2 || fail "apt cannot read $url $distribution"
for package in porelo-host porelo; do
    (cd "$dest" && apt-get "$@" download "$package=$version" >&2) \
        || fail "$url $distribution holds no $package $version"
    deb=$(ls "$dest/${package}_"*.deb)
    [ "$(dpkg-deb --field "$deb" Version)" = "$version" ] || fail "$deb is not $package $version"
done
deb=$(ls "$dest"/porelo-host_*.deb)
printf '%s\n' "$deb"
