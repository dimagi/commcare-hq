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
    local lockfile=migrations.lock
    local cmd=(make migrations.lock)
    log_group_begin "Check: ${cmd[*]}"
    "${cmd[@]}" >/dev/null  # don't output the diff twice
    git update-index -q --refresh
    if ! git diff --exit-code HEAD -- "$lockfile"; then
        # dirty
        log_fail "Frozen migrations are inconsistent.  Did you run '${cmd[*]}'?"
        #git checkout "$lockfile"  # (don't) clean up
        return 1
    fi
    # clean
    log_success "frozen migrations ok"
    log_group_end  # only log group end on success (prevents group collapse on failure)
}


main "$@"
