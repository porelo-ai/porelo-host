#!/bin/bash
# Molecule's registry, as a host admin keeps one: owners.yml naming the host admin, each person's card signed by their
# own key, the host's card and access file signed by the host admin, every commit SSH-signed by the host admin's key.
# Fixture keys without a passphrase sign from their files; no agent, vault or network is needed. Each run commits only
# what changed, on top of what is there, so a sync of the new bundle moves forward; it ends with the bundle checked as
# the host checks it.
#
# Usage: registry-bundle.sh DIR HOST ADDRESS HOST_KEY_PUB ADMIN [LOGIN[=revoked]]...
#   DIR       the work directory: DIR/<login> and DIR/<login>.pub are each person's fixture key, DIR/repo the registry
#             and DIR/registry.bundle the bundle written
#   ADMIN     the host admin's login, owner of the registry and admin of the host
#   LOGIN     each person the host's access file names as an admin, the host admin included or not
# PROJECTS, if set, is "name:admin ..." for the access file's projects.
set -euo pipefail
dir=$1 host=$2 address=$3 host_key=$4 admin=$5
shift 5
repo=$dir/repo
line() { cut -d' ' -f1,2 "$1"; }
fp() { ssh-keygen -lf "$1" | cut -d' ' -f2; }
g() {
    git -C "$repo" -c gpg.format=ssh -c user.signingkey="$dir/$admin" -c commit.gpgsign=true \
        -c user.name="$admin" -c user.email="$admin@$host" "$@"
}
commit() { # message paths...
    local message=$1
    shift
    g add -- "$@"
    if ! g diff --cached --quiet; then
        g commit -q -m "$message"
    fi
}
sign() { # body key out
    ssh-keygen -q -Y sign -n porelo -f "$2" "$1" < /dev/null
    cat "$1" "$1.sig" > "$3"
    rm -f "$1" "$1.sig"
}

if [ ! -d "$repo/.git" ]; then
    git init -q -b main "$repo"
    cat > "$repo/owners.yml" <<EOF
owners:
  - login: $admin
    key: "$(line "$dir/$admin.pub")"
host_admins:
  $host:
    - login: $admin
      key: "$(line "$dir/$admin.pub")"
EOF
    commit "Found the registry with $admin as its owner" owners.yml
fi
mkdir -p "$repo/people" "$repo/hosts/$host"

for login in "$admin" "$@"; do
    [ "$login" = "${login%=revoked}" ] || continue
    [ -f "$repo/people/$login.card" ] && continue
    {
        printf 'login: "%s"\nname: "%s"\nkey: "%s"\n' "$login" "$login" "$(line "$dir/$login.pub")"
        printf 'created: "%s"\nexpires: "%s"\n' "$(date -u +%F)" "$(date -u -d '+30 days' +%F)"
    } > "$repo/people/$login.card.body"
    sign "$repo/people/$login.card.body" "$dir/$login" "$repo/people/$login.card"
    commit "File $login's card" "people/$login.card"
done

if [ ! -f "$repo/hosts/$host/card" ]; then
    {
        printf 'host: "%s"\naddress: "%s"\nssh_port: 22\n' "$host" "$address"
        printf 'ssh_host_key: "%s"\n' "$(line "$host_key")"
        printf 'services:\n  forge:\n    web_port: 3000\n    git_port: 3001\n  matrix:\n    port: 8448\n'
    } > "$repo/hosts/$host/card.body"
    sign "$repo/hosts/$host/card.body" "$dir/$admin" "$repo/hosts/$host/card"
    commit "File the card of $host" "hosts/$host/card"
fi

# A person named LOGIN=revoked stays in the access file with their card removed: verify answers them revoked.
{
    echo "admins:"
    for login in "$@"; do
        printf '  %s: "%s"\n' "${login%=revoked}" "$(fp "$dir/${login%=revoked}.pub")"
    done
    echo "projects:"
    for project in ${PROJECTS:-}; do
        printf '  - name: %s\n    admin: %s\n    access_repository: "ssh://%s/%s/access.git"\n' \
            "${project%%:*}" "${project#*:}" "$host" "${project%%:*}"
    done
    [ -n "${PROJECTS:-}" ] || echo "  []"
} > "$repo/hosts/$host/access.yml"
for login in "$@"; do
    if [ "$login" != "${login%=revoked}" ]; then
        g rm -q --ignore-unmatch -- "people/${login%=revoked}.card"
    fi
done
# The removed cards go in the same commit as the access file.
commit "Admit the host's persons on $host" "hosts/$host/access.yml"

rm -f "$dir/registry.bundle"
git -C "$repo" bundle create -q "$dir/registry.bundle" main
porelo registry verify --repository "$dir/registry.bundle" --host "$host" --pinned "$(fp "$dir/$admin.pub")" \
    --json > "$dir/registry.verified"
git -C "$repo" rev-parse HEAD
