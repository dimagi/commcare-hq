#!/usr/bin/env bash
set -e

# source utils for logging functions log_group_{begin,end} and log_{success,fail}
source ./scripts/bash-utils.sh


function main {
    local retcode=0
    check_makemigrations  || retcode=$(( $retcode + 1 ))
    check_migrations_list || retcode=$(( $retcode + 1 ))
    return $retcode
}


function check_makemigrations {
    # check makemigrations
    local cmd=(./manage.py makemigrations)
    log_group_begin "Check: ${cmd[*]}"
    if ! "${cmd[@]}" --noinput --check; then
        # Changes
        log_fail "Migrations are missing.  Did you run '${cmd[*]}'?"
        return 1
    fi
    # No changes
    log_success "makemigrations ok"
    log_group_end  # only log group end on success (prevents group collapse on failure)
}


function check_migrations_list {
    # ensure migrations lockfile is consistent with actual migrations list
    local cmd=(./manage.py makemigrations --lock-check)
    log_group_begin "Check: ${cmd[*]}"
    if ! "${cmd[@]}"; then
        # lock file is inconsistent, show a diff because it's useful
        local tmpfile=$(mktemp)
        local diffopts=()
        ./manage.py makemigrations --lock-update --lock-path="$tmpfile"
        if diff --color /dev/null /dev/null >/dev/null 2>&1; then
            diffopts+=( --color )
        fi
        diff "${diffopts[@]}" -su migrations.lock "$tmpfile" || true
        rm -f "$tmpfile"
        log_fail "Frozen migrations are inconsistent.  You can use the" \
            "'makemigrations --lock-update' management command to refresh them."
        return 1
    fi
    # clean
    log_success "frozen migrations ok"
    log_group_end  # only log group end on success (prevents group collapse on failure)
}


main "$@"
