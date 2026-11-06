#!/bin/sh
# Rehearses an agent's move before a host is rented: a throwaway VM on this machine's libvirt, made by the same code as
# Molecule's test VM, with `up` run on it from this checkout's collection, the forge on and no pool. The organization is
# Molecule's stand-in unless a machine file for a real one is given, so by default nothing outside is touched. `down`
# runs the host's own down, then deletes exactly this run's VM, believed only as libvirt lists none of it. A real
# organization keeps the host's read key on its repositories: nobody takes it off but the repositories' owner.
# usage: build/rehearse-move.sh start [--machine-file <file>] [--cpus <n>] [--memory <GiB>] [--disk <GiB>]
#                                                              the VM made (8, 16, 80 by default) and up run on it
#        build/rehearse-move.sh ssh [<command>...]               the VM's admin login, with the run's keys
#        build/rehearse-move.sh tunnel <login> <port>            build/room-tunnel.sh to the VM, with its host key
#        build/rehearse-move.sh down                             the host's down, then the VM deleted
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
export LIBVIRT_DEFAULT_URI=qemu:///system
# virsh's words are read below, so they must not be translated.
export LC_ALL=C
pool=images
prefix=porelo-host-rehearsal
state=$root/target/rehearsal
cache=$HOME/.porelo/cache
account=rehearsal
limit=300
vm=$root/roles/vm_pool/files/porelo-vm

say() { printf '%s\n' "$*" >&2; }
fail() { say "FAILED: $*"; exit 1; }
usage() { fail "usage: $0 start [--machine-file <file>] [--cpus <n>] [--memory <GiB>] [--disk <GiB>] | ssh [<command>...] | tunnel <login> <port> | down"; }

# What libvirt lists of any rehearsal: its domains and volumes, one name a line.
listed() {
    domains=$(virsh list --all --name) || fail 'could not list libvirt domains'
    volumes=$(virsh vol-list "$pool") || fail 'could not list libvirt volumes'
    printf '%s\n%s\n' "$domains" "$(printf '%s\n' "$volumes" | awk 'NR > 2 {print $1}')" | grep "^$prefix-" || true
}

address() { # the VM's address from the run's record, refused unless it is one IPv4 address
    found=$(cat "$state/address") || fail "no rehearsal in $state"
    case $found in *'
'*) fail "no address in $state" ;; esac
    printf '%s\n' "$found" | grep -Eqx '[0-9]{1,3}(\.[0-9]{1,3}){3}' || fail "no address in $state: $found"
    printf '%s\n' "$found"
}

on_vm() { # <command>..., with standard input passed on; -- keeps a command from reading as ssh's own option
    at=$(address)
    ssh -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=5 -i "$state/id_ed25519" \
        -o UserKnownHostsFile="$state/known_hosts" -o StrictHostKeyChecking=yes -- "$account@$at" "$@"
}

recorded() { # the VM's name from the run's record, refused unless it is a rehearsal's
    found=$(cat "$state/name") || fail "no rehearsal in $state; nothing to take down"
    case $found in *'
'*) fail "$state/name holds no rehearsal's name" ;; esac
    printf '%s\n' "$found" | grep -Eqx "$prefix-[0-9]{8}t[0-9]{6}z" || fail "$state/name holds no rehearsal's name: $found"
    printf '%s\n' "$found"
}

start() {
    machine_file= cpus=8 memory=16 disk=80
    while [ $# -gt 0 ]; do
        [ $# -ge 2 ] || usage
        case $1 in
            --machine-file) machine_file=$2 ;;
            --cpus) cpus=$2 ;;
            --memory) memory=$2 ;;
            --disk) disk=$2 ;;
            *) usage ;;
        esac
        shift 2
    done
    for size in "$cpus" "$memory" "$disk"; do
        case $size in *'
'*) usage ;; esac
        printf '%s\n' "$size" | grep -Eqx '[1-9][0-9]{0,3}' || fail "'$size' is no size: a whole number from 1"
    done
    if [ -n "$machine_file" ] && ! { [ -f "$machine_file" ] && [ -r "$machine_file" ]; }; then
        fail "no readable machine file at $machine_file"
    fi
    [ ! -e "$state" ] || fail "$state is there from an earlier run; run down, or remove it once libvirt lists no rehearsal"
    left=$(listed)
    [ -z "$left" ] || { say "REFUSED: an earlier rehearsal left these; run down or delete them first:"; printf '    %s\n' "$left" >&2; exit 1; }

    name=$prefix-$(date -u +%Y%m%dt%H%M%Sz)
    made=
    image=
    finish() {
        status=$?
        trap - EXIT INT TERM
        if [ "$status" != 0 ]; then
            [ -z "$image" ] || rm -f "$image.part"
            [ -z "$made" ] || "$vm" delete "$name" || true
            left=$(listed)
            if [ -n "$left" ]; then
                say "start failed; LEFT BEHIND, the run's files in $state: $left"
                exit 1
            fi
            rm -rf "$state"
            say "start failed; libvirt lists nothing of $name"
        fi
        exit "$status"
    }
    trap finish EXIT
    trap 'exit 130' INT TERM

    read -r url digest < "$root/build/test-image"
    printf '%s\n' "$digest" | grep -Eqx '[0-9a-f]{64}' || fail "build/test-image names no SHA-256: $digest"
    image=$cache/${url##*/}.$digest
    if [ ! -f "$image" ]; then
        sums=$(curl -fsSL "${url%/*}/SHA256SUMS") || fail "could not read ${url%/*}/SHA256SUMS"
        printf '%s\n' "$sums" | grep -qx "$digest \*${url##*/}" \
            || fail "Ubuntu's SHA256SUMS does not name $digest for ${url##*/}"
        mkdir -p "$cache"
        curl -fsSL --retry 3 -o "$image.part" "$url" || fail "could not download $url"
        mv "$image.part" "$image"
    fi
    [ "$(sha256sum "$image" | cut -d' ' -f1)" = "$digest" ] || fail "$image does not have the digest $digest"
    base=porelo-host-base-$(printf '%s' "$digest" | cut -c1-12).qcow2
    "$vm" base "$image" "$digest" "$base" >/dev/null

    mkdir -p "$state"
    chmod 700 "$state"
    echo "$name" > "$state/name"
    ssh-keygen -q -t ed25519 -N '' -C "$name" -f "$state/id_ed25519"
    ssh-keygen -q -t ed25519 -N '' -C "$name" -f "$state/host_ed25519"
    "$vm" seed "$state" "$name" "$account" "$state/id_ed25519.pub" "$state/host_ed25519"
    "$root/build/tools.sh" ansible-galaxy collection build --force --output-path target/rehearsal >/dev/null
    tarball=$(ls "$state"/porelo-host-*.tar.gz)

    # Marked before it is made, so a half-made VM is deleted too.
    made=yes
    # ubuntu25.10: osinfo-db as Ubuntu 26.04 ships it knows no ubuntu26.04 yet.
    PORELO_VM_DISK=${disk}G "$vm" make "$name" "$base" "$state" $((memory * 1024)) "$cpus" ubuntu25.10
    started=$(date +%s)
    "$vm" address "$name" "$limit" > "$state/address"
    printf '%s %s\n' "$(cat "$state/address")" "$(cut -d' ' -f1,2 "$state/host_ed25519.pub")" > "$state/known_hosts"
    until on_vm true < /dev/null 2>/dev/null; do
        [ $(($(date +%s) - started)) -lt $limit ] || fail "$name took no ssh login within $limit s"
        sleep 3
    done
    on_vm cloud-init status --wait < /dev/null >/dev/null 2>&1 \
        || fail "cloud-init on $name did not finish cleanly: $(on_vm cloud-init status --long < /dev/null 2>&1)"
    say "$name is up at $(cat "$state/address") after $(($(date +%s) - started)) s"

    on_vm 'cat > /tmp/porelo-host.tar.gz' < "$tarball"
    if [ -n "$machine_file" ]; then
        on_vm sudo install -D -m 0600 -o root -g root /dev/stdin /etc/porelo-host/setup/machine.yml < "$machine_file"
    fi
    # As Molecule's converge does it for `host up`: Ubuntu's ansible-core, the collection, the admin's key pinned for
    # root and kept for this login, the inventory, the stand-in's machine file unless one was given, then up.
    on_vm sudo bash -s "$account" "${machine_file:+given}" <<'EOF'
set -euo pipefail
account=$1 given=${2:-}
# ssh passes this machine's LC_ALL=C on, and Ansible refuses any locale but UTF-8.
export DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8
apt-get -o DPkg::Lock::Timeout=300 update -qq
apt-get -o DPkg::Lock::Timeout=300 install -y -qq ansible-core >/dev/null
install -m 0600 /tmp/porelo-host.tar.gz /root/porelo-host.tar.gz
rm -f /tmp/porelo-host.tar.gz
ansible-galaxy collection install --force /root/porelo-host.tar.gz >/dev/null
umask 077
mkdir -p /root/.ssh /etc/porelo-host/setup
install -d -m 0755 /etc/ssh/authorized_keys
key=$(awk '$1 == "ssh-ed25519" { print $1 " " $2; exit }' "/home/$account/.ssh/authorized_keys")
[ -n "$key" ]
printf '%s\n' "$key" > /root/.ssh/authorized_keys
printf '%s\n' "$key" > "/etc/ssh/authorized_keys/$account"
chmod 0644 "/etc/ssh/authorized_keys/$account"
cat > /root/porelo-host-inventory.yml <<INVENTORY
all:
  hosts:
    localhost:
  vars:
    porelo_host_inventory_version: 2
    porelo_host_name: rehearsal
    porelo_host_network: 7
    porelo_host_distribution: snapshots
    porelo_host_forge: true
    porelo_host_kvm: false
INVENTORY
if [ -z "$given" ]; then
    # The stand-in's central organization is the host's own forge, as in Molecule.
    printf '    forge_migrations_allow_local: true\n' >> /root/porelo-host-inventory.yml
    [ -e /root/rehearsal-hostadmin ] || ssh-keygen -q -t ed25519 -N "" -C "" -f /root/rehearsal-hostadmin
    hostkey=$(cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub)
    admin=$(cut -d' ' -f1,2 /root/rehearsal-hostadmin.pub)
    cat > /etc/porelo-host/setup/machine.yml <<MACHINE
organization:
  known_hosts: |
    central.example $hostkey
  pin: |
    hostadmin $admin
  settings: |
    organization: {address: 'git@central.example:acme/organization.git', forge: central.example}
MACHINE
fi
# up writes files others must read, apt's key among them, as under a host's default umask.
umask 022
status=0
ANSIBLE_STDOUT_CALLBACK=porelo.host.lines \
    ansible-playbook -c local -i /root/porelo-host-inventory.yml porelo.host.up > /root/rehearsal-up.lines || status=$?
# An up is believed only by its lines: none failed and none waits on the person.
python3 -Ic 'import json, sys
lines = [json.loads(line) for line in open(sys.argv[1]) if line.strip()]
bad = [line for line in lines if line.get("state") in ("failed", "waiting")]
summary = any(line.get("state") == "host" for line in lines)
for line in bad:
    print(json.dumps(line), file=sys.stderr)
if not summary:
    print("up wrote no summary of the host", file=sys.stderr)
sys.exit(1 if bad or not summary else 0)' /root/rehearsal-up.lines || { [ "$status" != 0 ] || status=1; }
[ "$status" = 0 ] || { echo "up answered $status" >&2; tail -n 5 /root/rehearsal-up.lines >&2; exit 1; }
EOF
    say "up ran on $name; its lines are in /root/rehearsal-up.lines there"
}

down() {
    name=$(recorded)
    # The host's own down first, as on a rented host; a VM that does not run has nothing left to take down in it.
    if virsh domstate "$name" 2>/dev/null | grep -qx running; then
        on_vm sudo bash -s <<'EOF' || fail "down on $name failed; the VM is kept, run down again"
set -uo pipefail
status=0
ANSIBLE_STDOUT_CALLBACK=porelo.host.lines LC_ALL=C.UTF-8 \
    ansible-playbook -c local -i /root/porelo-host-inventory.yml porelo.host.down > /root/rehearsal-down.lines || status=$?
[ "$status" = 0 ] || { echo "down answered $status" >&2; grep '"failed"' /root/rehearsal-down.lines >&2; exit 1; }
EOF
    fi
    "$vm" delete "$name"
    left=$(listed)
    [ -z "$left" ] || fail "LEFT BEHIND, delete by hand: $left"
    rm -rf "$state"
    say "removed $name, its disk and its seed; libvirt lists no rehearsal"
}

[ $# -ge 1 ] || usage
verb=$1
shift
case "$verb" in
    start) start "$@" ;;
    ssh) on_vm "$@" ;;
    tunnel)
        [ $# -eq 2 ] || usage
        at=$(address)
        real=$(command -v ssh) || fail "no ssh on PATH"
        # room-tunnel.sh takes ssh's own defaults; a fixed wrapper first on its PATH adds this run's host key, and
        # refuses once down has removed it rather than falling back to the person's own known hosts.
        shim=$state/tunnel-bin
        mkdir -p "$shim"
        cat > "$shim/ssh" <<'EOF'
#!/bin/sh
[ -f "$REHEARSAL_KNOWN_HOSTS" ] || { echo "the rehearsal's host key is gone: $REHEARSAL_KNOWN_HOSTS" >&2; exit 1; }
exec "$REHEARSAL_SSH" -o "UserKnownHostsFile=$REHEARSAL_KNOWN_HOSTS" -o StrictHostKeyChecking=yes "$@"
EOF
        chmod 0700 "$shim/ssh"
        REHEARSAL_SSH=$real REHEARSAL_KNOWN_HOSTS=$state/known_hosts PATH=$shim:$PATH \
            exec "$root/build/room-tunnel.sh" "$1" "$at" "$2" ;;
    down) down ;;
    *) usage ;;
esac
