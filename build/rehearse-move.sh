#!/bin/sh
# Rehearses an agent's move before a host is rented: a throwaway VM on this machine's libvirt, made by the same code as
# Molecule's test VM, with `up` run on it from this checkout's collection, the forge on and no pool. The organization is
# Molecule's stand-in unless a machine file for a real one is given, so by default nothing outside is touched. `down`
# runs the host's own down, then deletes exactly this run's VM, believed only as libvirt lists none of it. A real
# organization keeps the host's read key on its repositories: nobody takes it off but the repositories' owner.
# `rented` rehearses check, up and down on an existing server, with a pinned key and a report outside this checkout.
# usage: build/rehearse-move.sh start [--machine-file <file> | --bare] [--cpus <n>] [--memory <GiB>] [--disk <GiB>]
#                                                              the VM made (8, 16, 80 by default) and up run on it;
#                                                              bare, without up, for a person's window to prepare
#        build/rehearse-move.sh ssh [<command>...]               the VM's admin login, with the run's keys
#        build/rehearse-move.sh tunnel <login> <port>            build/room-tunnel.sh to the VM, with its host key
#        build/rehearse-move.sh down                             the host's down, then the VM deleted
#        build/rehearse-move.sh rented <address> --key <file> [--login <user>]
#                                    [--machine-file <file>] [--order-time <UTC>] [--zone <name>]
#                                                              check, up and down on a server already rented
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
vm=$root/build/porelo-vm

say() { printf '%s\n' "$*" >&2; }
fail() { say "FAILED: $*"; exit 1; }
usage() { fail "usage: $0 start [--machine-file <file> | --bare] [--cpus <n>] [--memory <GiB>] [--disk <GiB>] | ssh [<command>...] | tunnel <login> <port> | down | rented <address> --key <file> [--login <user>] [--machine-file <file>] [--order-time <UTC>] [--zone <name>] [--org <program> --org-key <public key file> --person <login> --person-agent <socket> --central-token <program> --project <name> [--repository <name>] [--retire-host <host>] [--provider-keys <directory>]] | rented-resume"; }

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
    machine_file='' bare='' cpus=8 memory=16 disk=80
    while [ $# -gt 0 ]; do
        if [ "$1" = --bare ]; then
            bare=yes
            shift
            continue
        fi
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
    [ -z "$bare" ] || [ -z "$machine_file" ] || usage
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
    if [ -z "$bare" ]; then
        "$root/build/tools.sh" ansible-galaxy collection build --force --output-path target/rehearsal >/dev/null
        tarball=$(ls "$state"/porelo-host-*.tar.gz)
        stage_packages
    fi

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
    if [ -n "$bare" ]; then
        # The host's sshd reads an account's keys only from /etc/ssh/authorized_keys once up has run; the run's own key
        # is pinned there, so ssh and a watch from here keep their way in. Nothing else is set up.
        on_vm sudo sh -s "$account" <<'EOF' || fail "the run's key could not be pinned on $name"
set -eu
umask 022
install -d -m 0755 /etc/ssh/authorized_keys
awk '$1 == "ssh-ed25519" { print $1 " " $2; exit }' "/home/$1/.ssh/authorized_keys" > "/etc/ssh/authorized_keys/$1"
[ -s "/etc/ssh/authorized_keys/$1" ]
EOF
        # A person's window prepares and takes down such a host; down here only deletes the VM.
        : > "$state/bare"
        say "bare, as a provider hands a server over: its host key $(ssh-keygen -lf "$state/host_ed25519.pub" | cut -d' ' -f2)"
        return
    fi

    prepare_host
    say "up ran on $name; its lines are in /root/rehearsal-up.lines there"
}

# With PORELO_HOST_DEB set, the host program and the packages beside it come from this checkout's staged set, as in
# Molecule; without it, up installs from the signed repository.
stage_packages() {
    packages_digest=
    [ -n "${PORELO_HOST_DEB:-}" ] || return 0
    rm -rf "$state/packages" "$state/packages.tar"
    sh "$root/build/stage-packages.sh" "$state/packages" 2>/dev/null || fail "the local packages could not be staged"
    tar -C "$state/packages" -cf "$state/packages.tar" .
    packages_digest=$(sha256sum "$state/packages/SHA256SUMS" | cut -d' ' -f1)
}

host_root() {
    if [ "${rented_mode:-}" = yes ]; then on_rented "$@"; else on_vm sudo "$@"; fi
}

setup_host() {
    given=stand-in
    [ -z "$machine_file" ] || given=given
    if [ "${rented_mode:-}" = yes ]; then
        # systemd owns the remote processes even when an interrupted ssh connection has already gone away.
        host_root systemd-run --quiet --wait --pipe --collect --unit="$unit" -p KillMode=control-group \
            bash -s "$account" "$given" rented "$kvm" "$staging" "$unit" "${packages_digest:-}"
    else
        host_root bash -s "$account" "$given" rehearsal false /tmp - "${packages_digest:-}"
    fi
}

prepare_host() {
    if [ "${rented_mode:-}" = yes ]; then
        host_root sh -s "$staging" "$unit" <<'EOF'
set -eu
[ "$(cat "$1/owner")" = "$2" ]
rm -f /root/porelo-host-inventory.yml /root/rehearsal-up.lines /root/rehearsal-down.lines
EOF
        # shellcheck disable=SC2016
        host_root sh -c '[ "$(cat "$1/owner")" = "$2" ] && cat > "$1/porelo-host.tar.gz"' sh "$staging" "$unit" < "$tarball"
    else
        on_vm 'cat > /tmp/porelo-host.tar.gz' < "$tarball"
    fi
    if [ -n "${packages_digest:-}" ]; then
        if [ "${rented_mode:-}" = yes ]; then
            # shellcheck disable=SC2016
            host_root sh -c '[ "$(cat "$1/owner")" = "$2" ] && cat > "$1/porelo-packages.tar"' sh "$staging" "$unit" \
                < "$state/packages.tar"
        else
            on_vm 'cat > /tmp/porelo-packages.tar' < "$state/packages.tar"
        fi
    fi
    if [ -n "$machine_file" ]; then
        if [ "${rented_mode:-}" = yes ]; then
            # shellcheck disable=SC2016
            host_root sh -c '[ "$(cat "$1/owner")" = "$2" ] && install -D -m 0600 -o root -g root /dev/stdin /etc/porelo-host/setup/machine.yml' \
                sh "$staging" "$unit" < "$machine_file"
        else
            host_root install -D -m 0600 -o root -g root /dev/stdin /etc/porelo-host/setup/machine.yml < "$machine_file"
        fi
    fi
    # As Molecule's converge does it for `host up`: Ubuntu's ansible-core, the collection, the admin's key pinned for
    # root and kept for this login, the inventory, the stand-in's machine file unless one was given, then up.
    setup_host <<'EOF'
set -euo pipefail
account=$1 given=${2:-} host_name=$3 kvm=$4 staging=$5 digest=${7:-}
if [ "$host_name" = rented ]; then [ "$(cat "$staging/owner")" = "$6" ]; fi
# ssh passes this machine's LC_ALL=C on, and Ansible refuses any locale but UTF-8.
export DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8
apt-get -o DPkg::Lock::Timeout=300 update -qq
apt-get -o DPkg::Lock::Timeout=300 install -y -qq ansible-core >/dev/null
install -m 0600 "$staging/porelo-host.tar.gz" /root/porelo-host.tar.gz
rm -f "$staging/porelo-host.tar.gz"
ansible-galaxy collection install --force /root/porelo-host.tar.gz >/dev/null
umask 077
mkdir -p /root/.ssh /etc/porelo-host/setup
install -d -m 0755 /etc/ssh/authorized_keys
if [ "$host_name" = rented ]; then
    key=$(cat "$staging/login.pub")
else
    key=$(awk '$1 == "ssh-ed25519" { print $1 " " $2; exit }' "/home/$account/.ssh/authorized_keys")
fi
[ -n "$key" ]
rm -f /root/.ssh/authorized_keys
printf '%s\n' "$key" > /root/.ssh/authorized_keys
chmod 0600 /root/.ssh/authorized_keys
rm -f "/etc/ssh/authorized_keys/$account"
printf '%s\n' "$key" > "/etc/ssh/authorized_keys/$account"
chmod 0644 "/etc/ssh/authorized_keys/$account"
cat > /root/porelo-host-inventory.yml.tmp <<INVENTORY
all:
  hosts:
    localhost:
  vars:
    porelo_host_inventory_version: 2
    porelo_host_name: $host_name
    porelo_host_network: 7
    porelo_host_distribution: snapshots
    porelo_host_forge: true
    porelo_host_kvm: $kvm
INVENTORY
if [ -n "$digest" ]; then
    # Each package set in a directory of its own, so a package left out of a later set is never installed from an older.
    printf '%s\n' "$digest" | grep -Eqx '[0-9a-f]{64}'
    packages=/root/porelo-packages-$digest
    rm -rf "$packages"
    install -d -m 0700 "$packages"
    tar -xf "$staging/porelo-packages.tar" -C "$packages"
    rm -f "$staging/porelo-packages.tar"
    (cd "$packages" && sha256sum --check --strict --quiet SHA256SUMS)
    [ "$(sha256sum "$packages/SHA256SUMS" | cut -d' ' -f1)" = "$digest" ]
    printf '    porelo_local_packages: %s\n' "$packages" >> /root/porelo-host-inventory.yml.tmp
    for package in porelo-host porelo; do
        [ -f "$packages/$package.version" ] || continue
        version=$(cat "$packages/$package.version")
        printf '%s\n' "$version" | grep -Eqx '[0-9][A-Za-z0-9.+:~_-]*'
        printf '    %s_version: "%s"\n' "$(printf '%s' "$package" | tr - _)" "$version" >> /root/porelo-host-inventory.yml.tmp
    done
fi
if [ "$given" != given ]; then
    # The stand-in's central organization is the host's own forge, as in Molecule.
    printf '    forge_migrations_allow_local: true\n' >> /root/porelo-host-inventory.yml.tmp
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
mv /root/porelo-host-inventory.yml.tmp /root/porelo-host-inventory.yml
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
}

down() {
    name=$(recorded)
    # The host's own down first, as on a rented host; a VM that does not run has nothing left to take down in it.
    if [ ! -e "$state/bare" ] && virsh domstate "$name" 2>/dev/null | grep -qx running; then
        on_vm sudo bash -s <<'EOF' || fail "down on $name failed; the VM is kept, run down again"
set -uo pipefail
# A host a person's window prepared is taken down by that window; only the rehearsal's own up is taken down here.
[ -f /root/porelo-host-inventory.yml ] || exit 0
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

on_rented() {
    if [ "$account" != root ]; then set -- sudo -n "$@"; fi
    # OpenSSH joins arguments into shell text; quote each one, including multi-line Python and empty arguments.
    remote=
    for argument do
        quoted=$(printf '%s' "$argument" | sed "s/'/'\\\\''/g")
        remote="$remote '$quoted'"
    done
    timeout --kill-after=2 "$ssh_limit" ssh -F /dev/null -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=5 -i "$key_file" \
        -o IdentityAgent=none -o UserKnownHostsFile="$state/known_hosts" -o GlobalKnownHostsFile=/dev/null \
        -o StrictHostKeyChecking="$trust" -o ControlMaster=no -o ControlPath=none -o ClearAllForwardings=yes \
        -- "$account@$server" "$remote"
}

rented_line() {
    printf '%s\n' "$*" >> "$report/steps"
    say "$*"
}

collect_tree() {
    stop_pids="$stop_pids $1"
    for children_file in /proc/"$1"/task/*/children; do
        [ -r "$children_file" ] || continue
        children=''
        IFS= read -r children 2>/dev/null < "$children_file" || true
        for child in $children; do collect_tree "$child"; done
    done
}

process_alive() {
    [ -r "/proc/$1/stat" ] || return 1
    process_stat=''
    IFS= read -r process_stat 2>/dev/null < "/proc/$1/stat" || true
    case ${process_stat##*) } in Z\ *|'') return 1 ;; esac
}

stop_tree() {
    # Snapshot descendants before TERM can reparent them, then signal the parent before its children.
    stop_pids=''
    collect_tree "$1"
    for stop_pid in $stop_pids; do kill -TERM "$stop_pid" 2>/dev/null || true; done
    attempts=0
    while [ "$attempts" -lt 50 ]; do
        live=no
        for stop_pid in $stop_pids; do
            if process_alive "$stop_pid"; then live=yes; fi
        done
        [ "$live" = yes ] || return 0
        sleep 0.1
        attempts=$((attempts + 1))
    done
    for stop_pid in $stop_pids; do
        if process_alive "$stop_pid"; then kill -KILL "$stop_pid" 2>/dev/null || true; fi
    done
}

rented_signal() {
    pending_reason=$1 pending_code=$2
    # A claim must finish so its reply can establish ownership before cleanup.
    if [ "${claiming:-no}" != yes ] && [ -n "$active" ]; then stop_tree "$active"; fi
}

rented_abort_pending() {
    [ "$pending_code" != 0 ] || return 0
    if [ -n "$current" ]; then
        rented_line "FAIL $current finish the step -> $pending_reason"
        current=''
    else
        rented_line "FAIL between steps after ${last_step:-none} -> $pending_reason"
    fi
    exit "$pending_code"
}

rented_step() {
    rented_abort_pending
    current=$1 asked=$2
    [ "$current" != check ] || check_started=yes
    shift 2
    (trap - EXIT INT TERM ALRM; "$@") < /dev/null > "$report/$current.log" 2>&1 &
    active=$!
    result=0
    rented_abort_pending
    wait "$active" || result=$?
    rented_abort_pending
    active=''
    completed=$current
    current=''
    last_step=$completed
    if [ "$result" = 77 ] && [ "${hook_step:-no}" = yes ]; then
        [ "$completed" != tasks ] || : > "$state/tasks-skipped"
        rented_line "SKIP $completed $(tail -n 1 "$report/$completed.log")"
        rented_abort_pending
        return 0
    fi
    if [ "$result" != 0 ]; then
        details=$report/$completed.log
        if [ "$completed" = check ] && [ -s "$report/check.out" ]; then details=$report/check.out; fi
        rented_line "FAIL $completed $asked -> exit $result; see $details"
        rented_hold_failure "$completed"
        exit "$result"
    fi
    if [ "$completed" = check ]; then
        check_passed=yes
        kvm=$(cat "$state/kvm")
        rented_line "OK check $asked -> kvm $kvm"
    else
        rented_line "OK $completed $asked -> exit 0"
    fi
    rented_abort_pending
}

rented_prepare_check() {
    # These positional arguments expand in the remote shell.
    # shellcheck disable=SC2016
    on_rented sh -c '[ "$(cat "$1/owner")" = "$2" ] && cat > "$1/login.pub"' sh "$staging" "$unit" < "$state/login.pub"
    # shellcheck disable=SC2016
    on_rented sh -c 'cat > "$1/porelo-host-check"' sh "$staging" < "$root/roles/check/files/porelo-host-check"
    limits=$(cat "$root/roles/check/files/limits.json")
    check_status=0
    on_rented python3 -I "$staging/porelo-host-check" --limits "$limits" \
        --choices '{"forge":true,"kvm":false,"ports":[3001]}' --wait-packages 300 \
        > "$report/check.out.tmp" || check_status=$?
    mv "$report/check.out.tmp" "$report/check.out"
    [ "$check_status" = 0 ] || return "$check_status"
    python3 -I -c 'import json,sys; a=json.load(open(sys.argv[1])); sys.exit(0 if a["ok"] is True and a["complete"] is True else 1)' "$report/check.out"
    # These optional observations do not make preflight fail on a machine without KVM.
    on_rented python3 -I -c 'import json,os
line = next((line for line in open("/proc/cpuinfo") if line.startswith("flags")), "")
print(json.dumps({"flags": sorted(set(line.split(":", 1)[-1].split()) & {"vmx", "svm"}), "device": os.path.exists("/dev/kvm")}))' \
        > "$report/kvm.out.tmp"
    mv "$report/kvm.out.tmp" "$report/kvm.out"
    python3 -I -c 'import json,sys
a=json.load(open(sys.argv[1]))
assert isinstance(a["flags"], list) and isinstance(a["device"], bool)
print(str(bool(set(a["flags"]) & {"vmx", "svm"}) and a["device"]).lower())' "$report/kvm.out" > "$state/kvm"
}

rented_up() {
    : > "$state/up-started"
    # A resumed run builds again, perhaps a new version; only this build's tarball may stand.
    rm -f "$state"/porelo-host-*.tar.gz
    "$root/build/tools.sh" ansible-galaxy collection build --force --output-path target/rented
    tarball=$(ls "$state"/porelo-host-*.tar.gz)
    stage_packages
    prepare_host
    on_rented cat /root/rehearsal-up.lines > "$report/up.lines.tmp"
    mv "$report/up.lines.tmp" "$report/up.lines"
    python3 -I -c 'import json,sys
rows=[json.loads(line) for line in open(sys.argv[1]) if line.strip()]
sys.exit(1 if not any(row.get("state") == "host" for row in rows) or any(row.get("state") in ("failed", "waiting") for row in rows) else 0)' "$report/up.lines"
}

rented_down() {
    on_rented bash -s "$unit" "$staging" <<'EOF'
set -euo pipefail
unit=$1 staging=$2
[ "$(cat "$staging/owner")" = "$unit" ]
units=$(systemctl list-units --all --plain --no-legend "$unit.service")
if [ -n "$units" ]; then
    systemctl stop "$unit"
    units=$(systemctl list-units --all --plain --no-legend "$unit.service")
    if [ -n "$units" ]; then
        case $(systemctl show --property=ActiveState --value "$unit") in inactive|failed) ;; *) exit 1 ;; esac
        systemctl reset-failed "$unit"
    fi
fi
# Artifacts travel on this connection, so a failed cleanup never needs another read from the host.
emit_file() {
    [ -f "$2" ] || return 0
    python3 -I -c 'import json,sys
with open(sys.argv[2]) as stream:
    print(json.dumps({"file":sys.argv[1], "content":stream.read()}))' "$1" "$2"
}
emit_file up.lines /root/rehearsal-up.lines
if [ -f /root/porelo-host-inventory.yml ]; then
    status=0
    ANSIBLE_STDOUT_CALLBACK=porelo.host.lines LC_ALL=C.UTF-8 \
        ansible-playbook -c local -i /root/porelo-host-inventory.yml porelo.host.down > /root/rehearsal-down.lines || status=$?
    printf '{"down_ran":true}\n'
    read_status=0
    emit_file down.lines /root/rehearsal-down.lines || read_status=$?
    [ "$status" = 0 ] || exit "$status"
    [ "$read_status" = 0 ] || exit "$read_status"
    python3 -I -c 'import json,sys
rows=[json.loads(line) for line in open(sys.argv[1]) if line.strip()]
sys.exit(1 if not rows or any(row.get("state") in ("failed", "waiting") for row in rows) else 0)' /root/rehearsal-down.lines
else
    printf '{"down_ran":false}\n'
fi
# down keeps installed software and its firewall; only this run-owned staging is removed.
rm -rf "$staging"
EOF
}

rented_save_artifacts() {
    python3 -I -c 'import json,os,pathlib,sys
report=pathlib.Path(sys.argv[1]); state=pathlib.Path(sys.argv[2]); ran=None
with open(report/"down.out") as stream:
    for line in stream:
        row=json.loads(line)
        if "file" in row:
            if row["file"] not in ("up.lines", "down.lines") or not isinstance(row["content"], str):
                raise ValueError("unexpected cleanup artifact")
            temporary=report/(row["file"]+".tmp")
            temporary.write_text(row["content"])
            os.replace(temporary, report/row["file"])
        elif isinstance(row.get("down_ran"), bool):
            ran=row["down_ran"]
        else:
            raise ValueError("unexpected cleanup answer")
if ran is None:
    raise ValueError("cleanup did not say whether down ran")
(state/"down-ran").write_text(str(ran).lower())' "$report" "$state"
}

rented_finish() {
    status=$?
    trap - EXIT
    cleanup_signal='' cleanup_interrupted=no
    trap 'cleanup_signal=INT; cleanup_interrupted=yes' INT
    trap 'cleanup_signal=TERM; cleanup_interrupted=yes' TERM
    trap 'cleanup_signal=ALRM; cleanup_interrupted=yes' ALRM
    if [ -n "$active" ]; then stop_tree "$active"; wait "$active" 2>/dev/null || true; active=''; fi
    if [ -n "$timer" ]; then stop_tree "$timer"; wait "$timer" 2>/dev/null || true; timer=''; fi
    ssh_limit=300
    if [ "$owned" = yes ]; then
        if [ "${phase_two:-no}" = yes ] && [ -f "$state/org-added" ]; then
            # As a person would: the host leaves the organization and follows it, which takes the persons' memberships
            # off, since down refuses a host where any are left.
            off_status=0
            rented_org_off
            rm -f "$state/org-added" "$state/org-carried"
            if [ "$off_status" = 0 ]; then
                if on_root porelo-host org follow >> "$report/org-off.log" 2>&1; then
                    rented_line 'OK org-follow the host followed the organization it left -> exit 0'
                else
                    rented_line "FAIL org-follow the host followed the organization it left -> exit $?; see $report/org-off.log"
                fi
            fi
        fi
        down_status=0
        (trap - EXIT INT TERM ALRM; rented_down) > "$report/down.out.tmp" 2> "$report/down.log" &
        active=$!
        while :; do
            cleanup_interrupted=no
            wait "$active" && down_status=0 || down_status=$?
            if [ "$cleanup_interrupted" = yes ] && kill -0 "$active" 2>/dev/null; then continue; fi
            break
        done
        active=''
        mv "$report/down.out.tmp" "$report/down.out"
        artifact_status=0
        rented_save_artifacts 2>> "$report/down.log" || artifact_status=$?
        if [ "$down_status" = 0 ] && [ "$artifact_status" != 0 ]; then down_status=$artifact_status; fi
        if [ -n "$cleanup_signal" ]; then
            rented_line "FAIL between steps during cleanup -> $cleanup_signal"
            [ "$status" != 0 ] || status=143
        fi
        if [ "$down_status" = 0 ]; then
            if [ "$(cat "$state/down-ran")" = true ]; then
                rented_line 'OK down run the host down -> exit 0; its lines hold no failed or waiting steps'
                down_message="the host's down ran, its software stays until the server is deleted"
            else
                if [ -f "$state/up-started" ]; then
                    down_message='up did not reach its inventory; packages it installed may stay until the server is deleted'
                elif [ "$check_started" = yes ] && [ "$check_passed" = no ]; then
                    down_message='check failed before up; up installed no packages'
                else
                    down_message='up did not start; up installed no packages'
                fi
                rented_line "SKIP down $down_message"
            fi
            rented_org_off
            rented_line 'SKIP read-keys the deploy keys at central are taken off by the operator'"'"'s own script'
            rm -rf "$state"
            deleted_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
            place=''
            [ -z "$zone" ] || place=" in zone $zone"
            rented_line "delete the server $server$place now ($deleted_at); $down_message"
        else
            rented_line "FAIL down run the host down -> exit $down_status; see $report/down.log and $report/down.lines"
            rented_org_off
            rented_line 'SKIP read-keys the deploy keys at central are taken off by the operator'"'"'s own script'
            rented_line "LEFT on server $server: host software, firewall and rehearsal files may remain at /etc/porelo-host and $staging; state in $state"
            status=$down_status
        fi
    else
        rented_line "LEFT on server $server: existing or unverified contents were left untouched; no down was run"
    fi
    exit "$status"
}

rented_phase_two_options() {
    phase_two=no
    if [ -z "$org_program$org_key$person$person_agent$central_token$project$retire_host" ]; then return 0; fi
    [ -n "$org_program" ] && [ -n "$org_key" ] && [ -n "$person" ] && [ -n "$person_agent" ] && [ -n "$central_token" ] \
        && [ -n "$project" ] \
        || fail 'phase 2 needs --org, --org-key, --person, --person-agent, --central-token and --project together'
    repository=${repository:-$project}
    for name in "$person" "$project" "$repository" ${retire_host:+"$retire_host"}; do
        case $name in -*|*[!a-z0-9-]*) fail "not a plain name: $name" ;; esac
    done
    [ "$retire_host" != rented ] || fail 'the host to retire cannot be this run'"'"'s own'
    for program in "$org_program" "$central_token"; do
        [ -f "$program" ] && [ -x "$program" ] || fail "no executable program at $program"
    done
    [ -S "$person_agent" ] || fail "no agent socket at $person_agent"
    if [ -n "$provider_keys" ]; then [ -d "$provider_keys" ] || fail "no provider key directory at $provider_keys"; fi
    # The refresh logs in as root (Core, 2026-11-10); the operator's public key alone goes to root, without its comment.
    [ -f "$org_key" ] && [ -r "$org_key" ] || fail "no readable operator key at $org_key"
    [ "$(awk 'END { print NR }' "$org_key")" = 1 ] || fail 'the operator key must be one line'
    org_public=$(awk '$1 == "ssh-ed25519" && $2 ~ /^[A-Za-z0-9+\/]+=*$/ {print $1 " " $2}' "$org_key")
    [ -n "$org_public" ] || fail 'the operator key must be one ssh-ed25519 public key'
    if [ -n "${PORELO_REHEARSAL_HOLD_FILE:-}" ]; then
        [ ! -e "$PORELO_REHEARSAL_HOLD_FILE" ] && [ ! -L "$PORELO_REHEARSAL_HOLD_FILE" ] \
            || fail "the hold file is there already: $PORELO_REHEARSAL_HOLD_FILE"
    fi
    phase_two=yes
}

# The organization's program, given by the person, run here with the test identity it carries.
on_org() {
    timeout --kill-after=5 300 "$org_program" org host "$@"
}

on_person() {
    remote=
    for argument do
        quoted=$(printf '%s' "$argument" | sed "s/'/'\\\\''/g")
        remote="$remote '$quoted'"
    done
    timeout --kill-after=2 "$ssh_limit" ssh -F /dev/null -o BatchMode=yes -o IdentitiesOnly=no -o ConnectTimeout=5 \
        -o IdentityAgent="$person_agent" -o IdentityFile=none -o UserKnownHostsFile="$state/known_hosts" -o GlobalKnownHostsFile=/dev/null \
        -o StrictHostKeyChecking=yes -o ControlMaster=no -o ControlPath=none -o ClearAllForwardings=yes \
        -- "$person@$server" "$remote"
}

# Root through the person's agent, whose key --org-key put among root's keys: the host's own org verbs are root's
# alone and never run through sudo. env -i drops the SSH session's variables, which the host program refuses.
on_root() {
    # The remote shell expands its own PATH.
    # shellcheck disable=SC2016
    remote='exec env -i PATH="$PATH"'
    for argument do
        quoted=$(printf '%s' "$argument" | sed "s/'/'\\\\''/g")
        remote="$remote '$quoted'"
    done
    timeout --kill-after=2 "$ssh_limit" ssh -F /dev/null -o BatchMode=yes -o IdentitiesOnly=no -o ConnectTimeout=5 \
        -o IdentityAgent="$person_agent" -o IdentityFile=none -o UserKnownHostsFile="$state/known_hosts" -o GlobalKnownHostsFile=/dev/null \
        -o StrictHostKeyChecking=yes -o ControlMaster=no -o ControlPath=none -o ClearAllForwardings=yes \
        -- "root@$server" "$remote"
}

# Root's keys are the file up made; a follow later writes the host admins' keys there, so a key it holds already stays.
rented_root_key() {
    # These positional arguments expand in the remote shell.
    # shellcheck disable=SC2016
    printf '%s\n' "$org_public" | on_rented sh -c 'set -eu
keys=/etc/ssh/authorized_keys/root
key=$(cat)
if [ ! -f "$keys" ] || [ -L "$keys" ]; then echo "up made no root key file at $keys"; exit 1; fi
if awk -v key="$key" '"'"'$1 " " $2 == key { found = 1 } END { exit !found }'"'"' "$keys"; then exit 0; fi
work=$(mktemp "$keys.XXXXXX")
trap '"'"'rm -f -- "$work"'"'"' EXIT
cat "$keys" > "$work"
if [ -s "$work" ] && [ -n "$(tail -c 1 "$work")" ]; then echo >> "$work"; fi
printf "%s\n" "$key" >> "$work"
chmod 0644 "$work"
mv -fT "$work" "$keys"'
}

rented_org() {
    change=rehearsal-$stamp
    # The report names the client the organization was changed with.
    timeout --kill-after=5 60 "$org_program" --version > "$report/org-client.version" 2>&1 \
        || { echo 'the organization program does not answer --version'; return 1; }
    sed 's/^/org client: /' "$report/org-client.version"
    rented_root_key
    if [ -n "$retire_host" ]; then
        on_org uncarry --id "$change-uncarry-$retire_host" "$retire_host" "$project"
        on_org remove --id "$change-remove-$retire_host" "$retire_host"
    fi
    host_key=$(awk 'NR == 1 && $2 == "ssh-ed25519" {print $2 " " $3}' "$state/known_hosts")
    [ -n "$host_key" ] || { echo 'no pinned ssh-ed25519 host key'; return 1; }
    # Marked before asking: an add or carry that answers an error may still have written the change.
    : > "$state/org-added"
    on_org add --id "$change-add" --admin="$person" rented
    on_org change --id "$change-change" --address="$server" --ssh-port=22 --host-key="$host_key" \
        --forge-web-port=3000 --forge-git-port=3001 rented
    : > "$state/org-carried"
    on_org carry --id "$change-carry" rented "$project"
}

rented_project() {
    # Again here: a resumed run's up rewrites root's keys before it reruns the project step.
    rented_root_key
    # The refresh has the host follow the organization; the follow itself is root's alone and never runs through sudo.
    on_org refresh --json rented
    tries=${PORELO_REHEARSAL_FOLLOW_TRIES:-90}
    pause=${PORELO_REHEARSAL_FOLLOW_PAUSE:-10}
    while :; do
        # One lost connection while the follow runs is waited out like a person not yet admitted.
        if on_root porelo-host org status --json > "$report/org-status.json.tmp"; then
            mv "$report/org-status.json.tmp" "$report/org-status.json"
        fi
        if [ -f "$report/org-status.json" ] && python3 -I -c 'import json,sys
status=json.load(open(sys.argv[1]))
person=next((row for row in status.get("persons", []) if row.get("login") == sys.argv[2]), {})
sys.exit(0 if person.get("state") == "active" and any(row.get("project") == sys.argv[3] for row in person.get("projects", [])) else 1)' \
            "$report/org-status.json" "$person" "$project"; then
            return 0
        fi
        tries=$((tries - 1))
        [ "$tries" -gt 0 ] || { echo "the follow did not admit $person to $project; its last answer, if any, is in $report/org-status.json"; return 1; }
        sleep "$pause"
    done
}

rented_stop() {
    if [ ! -f "$state/vault-passphrase" ]; then
        (umask 077; head -c 32 /dev/urandom | base64 > "$state/vault-passphrase")
    fi
    # The passphrase and the token travel on standard input alone; printf is the shell's own.
    encoded=$(base64 -w0 < "$state/vault-passphrase")
    printf 'vault-new %s\n' "$encoded" | on_person porelo host stop-secrets --stdin vault-new
    encoded=''
    on_person porelo host forge-token --if-forge
    # The client names the central token's vault entry after the forge's name, as forge.conf gives it.
    forge=$(on_rented sed -n 's/^name=//p' /etc/porelo-host/forge.conf)
    case $forge in ''|*[!a-z0-9.-]*) echo "no forge name in forge.conf: $forge"; return 1 ;; esac
    token=$("$central_token") || { echo 'the central token program failed'; return 1; }
    [ -n "$token" ] || { echo 'the central token program gave nothing'; return 1; }
    printf '%s\n' "$token" | on_person porelo vault put --json "$forge.central"
    token=''
}

# ST291: what root and the people's sudo rules run is the packaged porelo-host, and the collection left no old program.
rented_host_program() {
    # shellcheck disable=SC2016
    on_rented sh -c 'set -u
found=0
for old in /usr/local/sbin/porelo-host-person /usr/local/sbin/porelo-host-project /usr/local/sbin/porelo-host-push \
    /usr/local/libexec/porelo-forge-gate /usr/local/bin/porelo-host-forge-token /usr/local/bin/porelo-host-stop \
    /usr/local/sbin/porelo-host-forge-password /usr/local/sbin/porelo-host /usr/local/bin/porelo-host; do
    if [ -e "$old" ] || [ -L "$old" ]; then echo "an old host program is still there: $old"; found=1; fi
done
if grep -rlE "/usr/local/(s?bin|libexec)/porelo-(host|forge)" /etc/systemd/system /etc/sudoers.d 2>/dev/null; then
    echo "a unit or sudo rule above still runs an old host program"; found=1
fi
exit "$found"' || return 1
    # As root without the session's variables, which the host program refuses through sudo as well.
    on_root porelo-host --version
}

rented_hook() {
    known=$(cat "$state/known_hosts")
    REHEARSAL_STEP=$1 REHEARSAL_HOST=$server REHEARSAL_HOST_NAME=rented REHEARSAL_HOST_KEY=${known#* } \
        REHEARSAL_KNOWN_HOSTS=$state/known_hosts REHEARSAL_PERSON=$person REHEARSAL_PERSON_AGENT=$person_agent \
        REHEARSAL_ORG=$org_program REHEARSAL_PROJECT=$project REHEARSAL_REPOSITORY=$repository \
        REHEARSAL_PROVIDER_KEYS=$provider_keys REHEARSAL_REPORT=$report REHEARSAL_DEADLINE=$deadline \
        REHEARSAL_PERSON_SSH=$root/build/rehearse-person-ssh.sh \
        "$root/build/rehearse-steps/$1"
}

rented_push_pull() {
    on_person porelo host pull "$project"
    on_person porelo host push "$project"
    on_person porelo host central-state --json "$project" > "$report/central-state.json.tmp"
    mv "$report/central-state.json.tmp" "$report/central-state.json"
}

# HO165's measurement: the answers go into the report as they come, the token itself never.
rented_refused_token() {
    # The client names the central token's vault entry after the forge's name, as forge.conf gives it.
    forge=$(on_rented sed -n 's/^name=//p' /etc/porelo-host/forge.conf)
    case $forge in ''|*[!a-z0-9.-]*) echo "no forge name in forge.conf: $forge"; return 1 ;; esac
    out=$report/refused-token.answers
    : > "$out"
    measured=0
    answer() {
        expected=$1 label=$2
        shift 2
        code=0
        on_person porelo host push "$project" "$@" > "$report/refused-token.out" 2>&1 || code=$?
        { printf '== %s: porelo host push %s %s -> exit %s\n' "$label" "$project" "$*" "$code"
          cat "$report/refused-token.out"; } >> "$out"
        if [ "$code" != "$expected" ]; then echo "$label: exit $code, expected $expected"; measured=1; fi
    }
    answer 0 'by the project file name' "$repository"
    central=$(python3 -I -c 'import json, sys
def names(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "central" and isinstance(v, str) and "/" in v:
                yield v.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
            yield from names(v)
    elif isinstance(o, list):
        for v in o:
            yield from names(v)
print(next(iter(names(json.load(open(sys.argv[1])))), ""))' "$report/central-state.json" 2>/dev/null || true)
    if [ -n "$central" ] && [ "$central" != "$repository" ]; then
        answer 0 'by the central name' "$central"
    else
        echo "the central name is the same as the project file's, or central-state names none: ${central:-none}" >> "$out"
    fi
    answer 64 'by an unknown name' no-such-repository
    # The run's own token is read first, so that it can be put back whatever the refused push does.
    token=$("$central_token") || { echo 'the central token program failed'; return 1; }
    [ -n "$token" ] || { echo 'the central token program gave nothing'; return 1; }
    # A token the central forge refuses, then the run's own again; a printf of a fixed text, no secret.
    if printf 'porelo-rehearsal-refused-token\n' | on_person porelo vault put --json "$forge.central" > /dev/null; then
        answer 1 'with a refused token' "$repository"
        grep -q 'refused authentication (HTTP 401)' "$report/refused-token.out" \
            || { echo 'the refused push does not name the 401'; measured=1; }
    else
        echo 'the refused token could not be put'; measured=1
    fi
    restored=no
    for attempt in 1 2 3; do
        if printf '%s\n' "$token" | on_person porelo vault put --json "$forge.central" > /dev/null; then
            restored=yes
            break
        fi
        echo "putting the central token back failed, attempt $attempt"
        sleep 5
    done
    token=''
    [ "$restored" = yes ] || { echo "the person's vault keeps the refused central token"; return 1; }
    sed -n 's/^== //p' "$out"
    return "$measured"
}

rented_org_off() {
    rm -f "$state/vault-passphrase"
    [ "${phase_two:-no}" = yes ] && [ -f "$state/org-added" ] || return 0
    off_status=0
    if [ -f "$state/org-carried" ]; then
        on_org uncarry --id "rehearsal-$stamp-uncarry" rented "$project" >> "$report/org-off.log" 2>&1 || off_status=$?
    fi
    if [ "$off_status" = 0 ]; then
        on_org remove --id "rehearsal-$stamp-remove" rented >> "$report/org-off.log" 2>&1 || off_status=$?
    fi
    if [ "$off_status" = 0 ]; then
        rented_line 'OK org-off take the host rented out of the organization -> exit 0'
    else
        rented_line "FAIL org-off take the host rented out of the organization -> exit $off_status; see $report/org-off.log"
        if [ -f "$state/org-carried" ]; then
            rented_line 'LEFT in the organization: the host rented, its card and what it carries'
        else
            rented_line 'LEFT in the organization, unless its add wrote nothing: the host rented and its card'
        fi
        [ "$status" != 0 ] || status=$off_status
    fi
}

rented() {
    [ $# -ge 1 ] || usage
    server=$1
    shift
    key_file='' machine_file='' order_time='' account=root zone='' zone_given=no
    org_program='' org_key='' person='' person_agent='' central_token='' project='' retire_host='' repository=''
    provider_keys=''
    while [ $# -gt 0 ]; do
        [ $# -ge 2 ] || usage
        case $1 in
            --key) key_file=$2 ;;
            --login) account=$2 ;;
            --machine-file) machine_file=$2 ;;
            --order-time) order_time=$2 ;;
            --zone) zone=$2; zone_given=yes ;;
            --org) org_program=$2 ;;
            --org-key) org_key=$2 ;;
            --person) person=$2 ;;
            --person-agent) person_agent=$2 ;;
            --central-token) central_token=$2 ;;
            --project) project=$2 ;;
            --retire-host) retire_host=$2 ;;
            --repository) repository=$2 ;;
            --provider-keys) provider_keys=$2 ;;
            *) usage ;;
        esac
        shift 2
    done
    case $server in *'
'*) fail 'the address must be one IPv4 address' ;; esac
    printf '%s\n' "$server" | grep -Eqx '[0-9]{1,3}(\.[0-9]{1,3}){3}' || fail 'the address must be one IPv4 address'
    case $account in ''|*[!a-zA-Z0-9_-]*) fail 'the login must be one account name' ;; esac
    if [ "$zone_given" = yes ]; then
        case $zone in ''|*[!a-z0-9-]*) fail 'the zone must contain only lower-case letters, digits and hyphens' ;; esac
    fi
    [ -n "$key_file" ] && [ -f "$key_file" ] && [ -r "$key_file" ] || fail "no readable private key at $key_file"
    public_key=$(ssh-keygen -y -P '' -f "$key_file" < /dev/null) || fail 'could not read the private key'
    case $public_key in ssh-ed25519\ *) ;; *) fail 'the private key must have an ssh-ed25519 public half' ;; esac
    case $public_key in *'
'*) fail 'the private key must have one public half' ;; esac
    if [ -n "$machine_file" ]; then
        [ -f "$machine_file" ] && [ -r "$machine_file" ] || fail "no readable machine file at $machine_file"
    fi
    rented_phase_two_options
    now=$(date -u +%s)
    ordered=$now
    if [ -n "$order_time" ]; then
        case $order_time in *'
'*) fail 'order time must be ISO UTC' ;; esac
        printf '%s\n' "$order_time" | grep -Eqx '[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(:[0-9]{2})?Z' \
            || fail 'order time must be ISO UTC'
        ordered=$(date -u -d "$order_time" +%s) || fail "unparsable order time: $order_time"
        [ "$ordered" -le "$now" ] || fail 'order time is in the future'
    fi
    hard_stop=${PORELO_REHEARSAL_HARD_STOP_SECONDS:-19800}
    case $hard_stop in ''|*[!0-9]*) fail 'hard stop must be seconds as a whole number' ;; esac
    [ "${#hard_stop}" -le 8 ] || fail 'hard stop is too large'
    deadline=$((ordered + hard_stop))
    remaining=$((deadline - now))
    [ "$remaining" -gt 0 ] || fail 'hard stop has already passed since order time'
    state=$root/target/rented
    [ ! -e "$state" ] && [ ! -L "$state" ] || fail "$state is there from an earlier run; inspect it before removing it"
    umask 077
    mkdir -p "$root/target" "$HOME/.porelo/rehearsal"
    mkdir -m 700 "$state" || fail "$state is there from an earlier run"
    stamp=$(date -u +%Y%m%dt%H%M%Sz)
    report=$HOME/.porelo/rehearsal/$server-$stamp
    mkdir -m 700 "$report" || fail "report already exists: $report"
    printf '%s\n' "$report" > "$state/report"
    printf '%s\n' "$server" > "$state/address"
    printf '%s\n' "$public_key" > "$state/login.pub"
    : > "$state/known_hosts"
    : > "$report/steps"
    rented_mode=yes trust=accept-new owned=no active='' timer='' current=refuse-existing last_step=''
    pending_code=0 pending_reason=''
    check_started=no check_passed=no claiming=yes
    ssh_limit=5
    staging=/run/porelo-rehearsal
    unit=porelo-rehearsal-$stamp-$$
    trap rented_finish EXIT
    trap 'rented_signal INT 130' INT
    trap 'rented_signal TERM 143' TERM
    trap 'rented_signal "hard stop" 124' ALRM
    main=$$
    (sleep "$remaining"; kill -ALRM "$main") &
    timer=$!
    result=0
    on_rented sh -s "$staging" "$unit" > "$state/probe" <<'EOF' &
set -eu
staging=$1 token=$2
if test -e /etc/porelo-host || test -L /etc/porelo-host || test -e "$staging" || test -L "$staging"; then
    printf 'existing\n'
    exit 0
fi
if ! mkdir -m 700 "$staging"; then
    printf 'existing\n'
    exit 0
fi
printf '%s\n' "$token" > "$staging/owner"
printf 'claimed %s\n' "$token"
EOF
    active=$!
    # Signals record pending work but cannot abandon this bounded ownership exchange.
    while :; do
        result=0
        wait "$active" || result=$?
        kill -0 "$active" 2>/dev/null || break
    done
    active=''
    claiming=no
    ssh_limit=$((remaining + 5))
    trust=yes
    printf 'claimed %s\n' "$unit" > "$state/expected-claim"
    if ! cmp -s "$state/probe" "$state/expected-claim"; then
        rented_abort_pending
        current=''
        rented_line "FAIL refuse-existing claim an unused host -> exit $result; existing host or unconfirmed claim"
        exit 1
    fi
    owned=yes
    : > "$state/owns-host"
    current=''
    last_step=refuse-existing
    rented_line 'OK refuse-existing claim an unused host -> its staging and owner token were created'
    rented_abort_pending
    rented_step check 'run the host preflight and observe CPU flags and /dev/kvm' rented_prepare_check
    rented_steps up
}

# The steps from up on; a resumed run reruns up, for a fixed collection or packages, then goes on from its failed step.
rented_steps() {
    resume_from=$1 resume_reached=no
    rented_step up 'install the collection and judge up lines' rented_up
    if [ "$phase_two" = no ]; then
        for step in stop project judge push-pull; do
            rented_abort_pending
            rented_line "SKIP $step needs the test identity (phase 2)"
        done
        rented_abort_pending
        return 0
    fi
    if rented_due org; then rented_step org "put the host into the organization and carry $project" rented_org; fi
    if rented_due project; then
        rented_step project "refresh the host and wait for the follow to admit $person to $project" rented_project
    fi
    if rented_due stop; then
        rented_step stop "give $person's stop a new vault, a forge token and the central token" rented_stop
    fi
    if rented_due host-program; then
        rented_step host-program 'the host runs porelo-host and no old host program' rented_host_program
    fi
    # The steps other agents build: one executable each under build/rehearse-steps, called by the contract in
    # doc/testing.md; 0 is OK, 77 SKIP with its last line, anything else FAIL.
    # judge comes before window, which takes all the time left, while the tasks of the tasks step still run.
    for hook in tasks busy-room judge window; do
        rented_due "$hook" || continue
        [ "$hook" != tasks ] || rm -f "$state/tasks-skipped"
        if [ "$hook" != window ] && [ "$hook" != tasks ] && [ -f "$state/tasks-skipped" ]; then
            rented_abort_pending
            rented_line "SKIP $hook the tasks step was skipped"
            continue
        fi
        if [ ! -f "$root/build/rehearse-steps/$hook" ] || [ ! -x "$root/build/rehearse-steps/$hook" ]; then
            rented_abort_pending
            rented_line "SKIP $hook not built yet"
            [ "$hook" != tasks ] || : > "$state/tasks-skipped"
            continue
        fi
        hook_step=yes
        rented_step "$hook" "run build/rehearse-steps/$hook" rented_hook "$hook"
        hook_step=no
    done
    rented_abort_pending
    if rented_due push-pull; then
        rented_step push-pull "pull and push $project with central and read its central state" rented_push_pull
    fi
    if rented_due refused-token; then
        rented_step refused-token "push $project by its names, by an unknown one and with a refused token" \
            rented_refused_token
    fi
    if [ -n "${PORELO_REHEARSAL_HOLD_FILE:-}" ]; then
        # Another agent's live run on this host goes on until it removes the file; the hard stop still ends it.
        : > "$PORELO_REHEARSAL_HOLD_FILE"
        rented_line "HOLD hold the host stays up for another run until $PORELO_REHEARSAL_HOLD_FILE is removed"
        rented_step hold 'keep the host up until the hold file is removed' rented_hold
    fi
    rented_abort_pending
}

rented_hold() {
    while [ -e "$PORELO_REHEARSAL_HOLD_FILE" ]; do sleep 1; done
}

# A step a run resumes from, and every step after it, runs; the steps before it passed in the held run.
rented_due() {
    if [ "$resume_from" = up ] || [ "$resume_from" = "$1" ]; then resume_reached=yes; fi
    # The rerun up may change what the follow made, so a resume after the project step follows again first.
    if [ "$1" = project ]; then case $resume_from in up | org | project) ;; *) return 0 ;; esac; fi
    [ "$resume_reached" = yes ]
}

keep() {
    printf "%s='%s'\n" "$1" "$(printf '%s' "$2" | sed "s/'/'\\\\''/g")"
}

# A failed step after check keeps the host up while the hard stop allows, so it is fixed and rerun on the same server:
# removing the hold file lets down run; a resume file, written by the person who holds it, reruns from up.
rented_hold_failure() {
    failed=$1
    [ "${phase_two:-no}" = yes ] && [ -n "${PORELO_REHEARSAL_HOLD_FILE:-}" ] || return 0
    case $failed in refuse-existing|check|hold) return 0 ;; esac
    hold=$PORELO_REHEARSAL_HOLD_FILE
    : > "$hold"
    rented_line "HOLD failure the host stays up after $failed failed: remove $hold to run down, or write $hold.resume to rerun up and $failed on"
    while :; do
        current=hold
        (trap - EXIT INT TERM ALRM; while [ -e "$hold" ] && [ ! -e "$hold.resume" ]; do sleep 1; done) &
        active=$!
        rented_abort_pending
        wait "$active" || true
        active=''
        rented_abort_pending
        current=''
        [ -e "$hold.resume" ] || return 0
        rented_resume_request "$failed"
    done
}

# The resume file may name new packages, one PORELO_HOST_DEB or PORELO_HOST_PACKAGES line each, by absolute path.
rented_resume_request() {
    request=$hold.resume resume_step=$1
    set --
    refusal=''
    if [ ! -f "$request" ] || [ -L "$request" ] || [ "$(stat -c %u "$request")" != "$(id -u)" ]; then
        refusal='not a plain file of this account'
    else
        while IFS= read -r line || [ -n "$line" ]; do
            case $line in
                '') ;;
                PORELO_HOST_DEB=/*)
                    case $line in *[[:space:]]*) refusal="a path with a space: $line" ;; esac
                    [ -f "${line#*=}" ] || refusal="no package at ${line#*=}"
                    set -- "$@" "$line" ;;
                PORELO_HOST_PACKAGES=/*)
                    case $line in *[[:space:]]*) refusal="a path with a space: $line" ;; esac
                    [ -d "${line#*=}" ] || refusal="no package directory at ${line#*=}"
                    set -- "$@" "$line" ;;
                *) refusal="an unknown line: $line" ;;
            esac
        done < "$request"
    fi
    case " $* " in
        *' PORELO_HOST_PACKAGES='*) case " $* " in *' PORELO_HOST_DEB='*) ;; *) refusal='PORELO_HOST_PACKAGES needs a PORELO_HOST_DEB line' ;; esac ;;
    esac
    script=$root/build/rehearse-move.sh
    if [ -z "$refusal" ] && { [ ! -f "$script" ] || [ ! -x "$script" ]; }; then refusal="$script is not executable"; fi
    if [ -z "$refusal" ] && ! sh -n "$script"; then refusal="$script does not parse"; fi
    if [ -n "$refusal" ]; then
        rm -f "$request"
        rented_line "FAIL resume $refusal; the host stays held"
        return 0
    fi
    {
        keep server "$server"; keep account "$account"; keep key_file "$key_file"; keep zone "$zone"
        keep machine_file "$machine_file"
        keep report "$report"; keep stamp "$stamp"; keep unit "$unit"; keep staging "$staging"
        keep phase_two "$phase_two"; keep org_program "$org_program"; keep org_public "$org_public"
        keep person "$person"; keep person_agent "$person_agent"; keep central_token "$central_token"
        keep project "$project"; keep retire_host "$retire_host"; keep deadline "$deadline"
        keep repository "$repository"; keep provider_keys "$provider_keys"
        keep check_started "$check_started"; keep check_passed "$check_passed"; keep resume_from "$resume_step"
    } > "$state/resume.env"
    if [ -n "$timer" ]; then stop_tree "$timer"; wait "$timer" 2>/dev/null || true; timer=''; fi
    # A signal or the hard stop taken while the timer stopped ends the run here, with its down, not after the restart.
    rented_abort_pending
    trap - EXIT INT TERM ALRM
    rm -f "$hold" "$request"
    rented_line "RESUME the held run reruns up, then $resume_step and the steps after it, from $script"
    exec env "$@" "$script" rented-resume
}

rented_resume() {
    state=$root/target/rented
    [ -f "$state/resume.env" ] || fail 'no held run to resume'
    # shellcheck source=/dev/null
    . "$state/resume.env"
    rm -f "$state/resume.env"
    umask 077
    rented_mode=yes trust=yes owned=yes active='' timer='' current='' last_step=$resume_from
    kvm=$(cat "$state/kvm")
    pending_code=0 pending_reason='' claiming=no
    trap rented_finish EXIT
    trap 'rented_signal INT 130' INT
    trap 'rented_signal TERM 143' TERM
    trap 'rented_signal "hard stop" 124' ALRM
    main=$$
    now=$(date -u +%s)
    remaining=$((deadline - now))
    if [ "$remaining" -le 0 ]; then
        rented_line 'FAIL resume -> hard stop'
        exit 124
    fi
    ssh_limit=$((remaining + 5))
    (sleep "$remaining"; kill -ALRM "$main") &
    timer=$!
    rented_steps "$resume_from"
    rented_abort_pending
}

[ $# -ge 1 ] || usage
verb=$1
shift
case "$verb" in
    start) start "$@" ;;
    rented) rented "$@" ;;
    rented-resume) [ $# -eq 0 ] || usage; rented_resume ;;
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
