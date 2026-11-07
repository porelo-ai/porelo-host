# shellcheck shell=bash

forge_token_refuse() {
    printf 'porelo-host-forge-token: %s\n' "$1" >&2
    return "${2:-69}"
}

# Rotation invalidates the previous token, so the person's own tools need its replacement in the vault.
refresh_person_forge_token() {
    local forge_conf=$1 person_helper=$2 forge_owner=0
    local owner mode line forge_name='' forge_account='' accounts=0
    local_token=
    export -n local_token
    if [ ! -f "$forge_conf" ] || [ -L "$forge_conf" ] || [ ! -r "$forge_conf" ]; then
        forge_token_refuse 'the forge settings are not a readable plain file'
        return $?
    fi
    read -r owner mode < <(stat -c '%u %a' -- "$forge_conf") || {
        forge_token_refuse 'the forge settings could not be checked'
        return $?
    }
    if [ "$owner" != "$forge_owner" ] || ! [[ $mode =~ ^[0-7]{3,4}$ ]] || [ $((8#$mode & 8#022)) != 0 ]; then
        forge_token_refuse 'the forge settings must be writable by root alone'
        return $?
    fi
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            name=*) forge_name=${line#name=} ;;
            account=*) forge_account=${line#account=}; accounts=$((accounts + 1)) ;;
        esac
    done < "$forge_conf"
    # The organization writes an empty account even on hosts that run no forge.
    if [ "$accounts" -le 1 ] && [ -z "$forge_account" ] && [ "${3:-}" = --if-forge ]; then
        return 0
    fi
    if [ "$accounts" != 1 ] || ! [[ $forge_account =~ ^[a-z_][a-z0-9_-]{0,31}$ ]]; then
        forge_token_refuse 'the forge settings name no single valid forge account'
        return $?
    fi
    if ! [[ $forge_name =~ ^[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?$ ]]; then
        forge_token_refuse 'the forge settings name no valid forge'
        return $?
    fi

    # Neither the person's terminal nor a gathered push's central token may reach sudo's stdin.
    local_token=$(sudo -n "$person_helper" forge-token < /dev/null 2>/dev/null) || {
        local_token=
        forge_token_refuse "the person's forge token could not be made"
        return $?
    }
    if ! [[ $local_token =~ ^[0-9a-f]{40}$ ]]; then
        local_token=
        forge_token_refuse 'the host answered no valid forge token'
        return $?
    fi
    # A failing vault command may repeat its input in diagnostics; only this refusal reaches the terminal.
    if ! (set -o pipefail; printf '%s' "$local_token" | porelo vault put "$forge_name.person" > /dev/null 2>&1); then
        # The caller says it in its own words: a gathered push still uses this token and goes on.
        return 65
    fi
}
