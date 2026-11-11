#!/bin/sh
# Temporary, for Canonical's archive outage of 2026-11-11 (removed once Canonical is back): points apt's Ubuntu
# sources at a public mirror of the same suites. apt still checks every Release file against Ubuntu's keyring
# (Signed-By); only where the files come from changes. Run as root. A VM gets the same from
# build/apt-fallback.cloud-config.
set -eu
sources=/etc/apt/sources.list.d/ubuntu.sources
mirror=http://ftp.fau.de/ubuntu/
[ -f "$sources" ] || { echo "apt-fallback: no $sources" >&2; exit 1; }
sed -i -E "s#^URIs: .*#URIs: $mirror#" "$sources"
echo "apt-fallback: Ubuntu's suites from $mirror"
