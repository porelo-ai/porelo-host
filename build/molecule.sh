#!/bin/sh
# Runs a Molecule scenario against a VM made for this run through libvirt on this machine: Ubuntu 26.04 from the image
# build/test-image pins, nested KVM, a host key made for the run and accepted alone. It deletes exactly that VM, its
# disk and its seed afterwards, after a failure and on an interrupt too, and refuses to start over one an earlier run
# left. The downloaded image and its base volume are kept as a cache, named by their digest.
# usage: build/molecule.sh [<scenario>]
set -eu
scenario=${1:-default}
root=$(cd "$(dirname "$0")/.." && pwd)
export LIBVIRT_DEFAULT_URI=qemu:///system
# virsh's words are read below, so they must not be translated.
export LC_ALL=C
pool=images
prefix=porelo-host-molecule
run=$(date -u +%Y%m%dT%H%M%SZ)-$$
name=$prefix-$run
dir=$root/target/molecule/$run
cache=$HOME/.porelo/cache
limit=300

vm=$root/roles/vm_pool/files/porelo-vm
say() { printf '%s\n' "$*" >&2; }
fail() { say "FAILED: $*"; exit 1; }

# --- refuse leftovers -----------------------------------------------------------------------------------------------
left=$(virsh list --all --name | grep "^$prefix-" || true)
left="$left$(virsh vol-list "$pool" | awk '{print $1}' | grep "^$prefix-" || true)"
[ -z "$left" ] || { say "REFUSED: an earlier run left these; delete them first:"; printf '    %s\n' $left >&2; exit 1; }

# --- clean up exactly what this run made ----------------------------------------------------------------------------
made=
cleanup() {
    status=$?
    trap - EXIT INT TERM
    rm -rf "$dir"
    if [ -n "$made" ]; then
        "$vm" delete "$name" || exit 1
        say "removed what run $run made: $name, its disk and its seed; libvirt lists none of them"
    fi
    exit $status
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# --- the base image, by its pinned digest ----------------------------------------------------------------------------
read -r url digest < "$root/build/test-image"
printf '%s\n' "$digest" | grep -Eqx '[0-9a-f]{64}' || fail "build/test-image names no SHA-256: $digest"
sums=$(curl -fsSL "${url%/*}/SHA256SUMS") || fail "could not read ${url%/*}/SHA256SUMS"
printf '%s\n' "$sums" | grep -qx "$digest \*${url##*/}" \
    || fail "Ubuntu's SHA256SUMS does not name $digest for ${url##*/}"
image=$cache/${url##*/}.$digest
if [ ! -f "$image" ]; then
    mkdir -p "$cache"
    say "downloading ${url##*/} once, about 865 MB"
    curl -fsSL --retry 3 -o "$image.part" "$url" || fail "could not download $url"
    mv "$image.part" "$image"
fi
[ "$(sha256sum "$image" | cut -d' ' -f1)" = "$digest" ] || fail "$image does not have the digest $digest"
base=porelo-host-base-$(printf '%s' "$digest" | cut -c1-12).qcow2
"$vm" base "$image" "$digest" "$base" >/dev/null

# --- the run's keys and seed -----------------------------------------------------------------------------------------
mkdir -p "$dir"
chmod 700 "$dir"
ssh-keygen -q -t ed25519 -N '' -C "$name" -f "$dir/id_ed25519"
ssh-keygen -q -t ed25519 -N '' -C "$name" -f "$dir/host_ed25519"
"$vm" seed "$dir" "$name" molecule "$dir/id_ed25519.pub" "$dir/host_ed25519"

# --- the VM -----------------------------------------------------------------------------------------------------------
# Marked before it is made, so a half-made VM is deleted too; deleting what is not there changes nothing.
made=yes
# ubuntu25.10: osinfo-db as Ubuntu 26.04 ships it (0.20250606) knows no ubuntu26.04 yet.
# 6 GiB: the host's own services, and the VM pool's one VM nested inside it.
"$vm" make "$name" "$base" "$dir" 6144 4 ubuntu25.10
started=$(date +%s)
address=$("$vm" address "$name" "$limit")
printf '%s %s\n' "$address" "$(cut -d' ' -f1,2 "$dir/host_ed25519.pub")" > "$dir/known_hosts"
vm() {
    ssh -n -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=5 -i "$dir/id_ed25519" \
        -o UserKnownHostsFile="$dir/known_hosts" -o StrictHostKeyChecking=yes molecule@"$address" "$@"
}
until vm true 2>/dev/null; do
    [ $(($(date +%s) - started)) -lt $limit ] \
        || fail "$name at $address took no ssh login within $limit s: $(vm true 2>&1)"
    sleep 3
done
# Waited for once: anything but a clean finish - a schema warning too - is a fault of the seed, and waiting longer
# would not mend it.
vm cloud-init status --wait >/dev/null 2>&1 \
    || fail "cloud-init on $name did not finish cleanly: $(vm cloud-init status --long 2>&1)"
say "$name is up at $address after $(($(date +%s) - started)) s"

# --- the scenario -----------------------------------------------------------------------------------------------------
work=/work/ansible_collections/porelo/host
"$root/build/tools.sh" ansible-galaxy collection build --output-path "target/molecule/$run" >/dev/null
version=$(sed -n 's/^version: *//p' "$root/galaxy.yml")
cat > "$dir/inventory.yml" <<EOF
all:
  hosts:
    $name:
      ansible_host: $address
      ansible_user: molecule
      ansible_ssh_private_key_file: $work/target/molecule/$run/id_ed25519
      ansible_ssh_common_args: >-
        -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$work/target/molecule/$run/known_hosts
EOF
# Porelo's packages handed over from a build not yet published, in PORELO_HOST_PACKAGES: copied into the run, where
# converge installs them over the published ones after the first up.
packages=
if [ -n "${PORELO_HOST_PACKAGES:-}" ]; then
    set -- "$PORELO_HOST_PACKAGES"/*.deb
    [ -f "$1" ] || fail "PORELO_HOST_PACKAGES=$PORELO_HOST_PACKAGES holds no .deb"
    mkdir "$dir/packages"
    cp "$@" "$dir/packages/"
    say "Porelo's packages from $PORELO_HOST_PACKAGES, not the published ones:"
    (cd "$dir/packages" && sha256sum ./*.deb) >&2
    packages=$work/target/molecule/$run/packages
fi
PORELO_HOST_INVENTORY=$work/target/molecule/$run/inventory.yml \
PORELO_HOST_TARBALL=$work/target/molecule/$run/porelo-host-$version.tar.gz \
PORELO_HOST_VERSION=$version \
PORELO_HOST_PACKAGES=$packages \
PORELO_HOST_MOLECULE_POOL=${PORELO_HOST_MOLECULE_POOL:-on} \
    "$root/build/tools.sh" molecule test -s "$scenario"
