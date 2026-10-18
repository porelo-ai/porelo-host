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

say() { printf '%s\n' "$*" >&2; }
fail() { say "FAILED: $*"; exit 1; }

# --- refuse leftovers -----------------------------------------------------------------------------------------------
left=$(virsh list --all --name | grep "^$prefix-" || true)
left="$left$(virsh vol-list "$pool" | awk '{print $1}' | grep "^$prefix-" || true)"
[ -z "$left" ] || { say "REFUSED: an earlier run left these; delete them first:"; printf '    %s\n' $left >&2; exit 1; }

# --- clean up exactly what this run made ----------------------------------------------------------------------------
made_domain=; made_disk=; made_seed=
cleanup() {
    status=$?
    trap - EXIT INT TERM
    # Stopped before it is undefined: undefining a running domain only makes it transient, and it runs on.
    if [ -n "$made_domain" ]; then
        virsh destroy "$name" >/dev/null 2>&1 || true
        virsh undefine "$name" >/dev/null 2>&1 || true
    fi
    [ -z "$made_disk" ] || virsh vol-delete "$name.qcow2" --pool "$pool" >/dev/null 2>&1 || true
    [ -z "$made_seed" ] || virsh vol-delete "$name-seed.iso" --pool "$pool" >/dev/null 2>&1 || true
    rm -rf "$dir"
    # Believed only as seen: what libvirt still lists of this run is left behind, whatever the commands answered.
    kept="$(virsh list --all --name | grep -x "$name" || true) $(virsh vol-list "$pool" | awk '{print $1}' \
        | grep -x -e "$name.qcow2" -e "$name-seed.iso" || true)"
    if [ -n "$(printf '%s' "$kept" | tr -d ' ')" ]; then say "LEFT BEHIND, delete by hand:" $kept; exit 1; fi
    say "removed what run $run made: $name, its disk and its seed; libvirt lists none of them"
    exit $status
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# --- the base image, by its pinned digest ----------------------------------------------------------------------------
read -r url digest < "$root/build/test-image"
printf '%s\n' "$digest" | grep -Eqx '[0-9a-f]{64}' || fail "build/test-image names no SHA-256: $digest"
sums=$(curl -fsSL "${url%/*}/SHA256SUMS") || fail "could not read ${url%/*}/SHA256SUMS"
printf '%s\n' "$sums" | grep -qx "$digest \*${url##*/}" || fail "Ubuntu's SHA256SUMS does not name $digest for ${url##*/}"
image=$cache/${url##*/}.$digest
if [ ! -f "$image" ]; then
    mkdir -p "$cache"
    say "downloading ${url##*/} once, about 865 MB"
    curl -fsSL --retry 3 -o "$image.part" "$url" || fail "could not download $url"
    mv "$image.part" "$image"
fi
[ "$(sha256sum "$image" | cut -d' ' -f1)" = "$digest" ] || fail "$image does not have the digest $digest"
base=porelo-host-base-$(printf '%s' "$digest" | cut -c1-12).qcow2
if ! virsh vol-info "$base" --pool "$pool" >/dev/null 2>&1; then
    virsh vol-create-as "$pool" "$base" "$(stat -c %s "$image")" --format qcow2 >/dev/null
    virsh vol-upload "$base" "$image" --pool "$pool"
fi

# --- the run's keys and seed -----------------------------------------------------------------------------------------
mkdir -p "$dir"
chmod 700 "$dir"
ssh-keygen -q -t ed25519 -N '' -C "$name" -f "$dir/id_ed25519"
ssh-keygen -q -t ed25519 -N '' -C "$name" -f "$dir/host_ed25519"
{
    echo '#cloud-config'
    echo 'users:'
    echo '  - name: molecule'
    echo '    sudo: "ALL=(ALL) NOPASSWD:ALL"'
    echo '    shell: /bin/bash'
    echo "    ssh_authorized_keys: [\"$(cat "$dir/id_ed25519.pub")\"]"
    echo 'ssh_pwauth: false'
    echo 'ssh_deletekeys: true'
    echo 'ssh_genkeytypes: [ed25519]'
    echo 'ssh_keys:'
    echo '  ed25519_private: |'
    sed 's/^/    /' "$dir/host_ed25519"
    echo "  ed25519_public: \"$(cat "$dir/host_ed25519.pub")\""
} > "$dir/user-data"
printf 'instance-id: %s\nlocal-hostname: %s\n' "$name" "$name" > "$dir/meta-data"
xorriso -as mkisofs -quiet -o "$dir/seed.iso" -V cidata -J -r "$dir/user-data" "$dir/meta-data"

# --- the VM -----------------------------------------------------------------------------------------------------------
made_disk=yes
virsh vol-create-as "$pool" "$name.qcow2" 20G --format qcow2 --backing-vol "$base" --backing-vol-format qcow2 >/dev/null
made_seed=yes
virsh vol-create-as "$pool" "$name-seed.iso" "$(stat -c %s "$dir/seed.iso")" --format raw >/dev/null
virsh vol-upload "$name-seed.iso" "$dir/seed.iso" --pool "$pool"
made_domain=yes
virt-install --name "$name" --memory 4096 --vcpus 4 --cpu host-passthrough --import \
    --disk "vol=$pool/$name.qcow2,bus=virtio" --disk "vol=$pool/$name-seed.iso,device=cdrom" \
    --network network=default --osinfo ubuntu25.10 --graphics none --noautoconsole >/dev/null

started=$(date +%s)
address=
while [ -z "$address" ]; do
    [ $(($(date +%s) - started)) -lt $limit ] || fail "$name got no address within $limit s"
    [ "$(virsh domstate "$name")" = running ] || fail "$name is not running: $(virsh domstate "$name")"
    sleep 3
    address=$(virsh domifaddr "$name" --source lease | awk '/ipv4/ {sub("/.*", "", $4); print $4; exit}')
done
printf '%s %s\n' "$address" "$(cut -d' ' -f1,2 "$dir/host_ed25519.pub")" > "$dir/known_hosts"
vm() {
    ssh -n -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=5 -i "$dir/id_ed25519" \
        -o UserKnownHostsFile="$dir/known_hosts" -o StrictHostKeyChecking=yes molecule@"$address" "$@"
}
until vm true 2>/dev/null; do
    [ $(($(date +%s) - started)) -lt $limit ] || fail "$name at $address took no ssh login within $limit s: $(vm true 2>&1)"
    sleep 3
done
# Waited for once: anything but a clean finish - a schema warning too - is a fault of the seed, and waiting longer
# would not mend it.
vm cloud-init status --wait >/dev/null 2>&1 || fail "cloud-init on $name did not finish cleanly: $(vm cloud-init status --long 2>&1)"
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
PORELO_HOST_INVENTORY=$work/target/molecule/$run/inventory.yml \
PORELO_HOST_TARBALL=$work/target/molecule/$run/porelo-host-$version.tar.gz \
PORELO_HOST_VERSION=$version \
    "$root/build/tools.sh" molecule test -s "$scenario"
