#!/usr/bin/env bash
set -e

function main {
    local retcode=0
    check_makemigrations  || retcode=$(( $retcode + 1 ))
    check_migrations_list || retcode=$(( $retcode + 1 ))
    return $retcode
}


function check_makemigrations {
    # check makemigrations
    local cmd=(./manage.py makemigrations)
    log_color '0;33' "Checking: ${cmd[*]}"
    if ! "${cmd[@]}" --noinput --check; then
        # Changes
        log_color '0;31' "ERROR: Migrations are missing.  Did you run '${cmd[*]}'?"
        return 1
    fi
    # No changes
    log_color '0;32' "makemigrations ok"
}


function check_migrations_list {
    # ensure migrations lockfile is consistent with actual migrations list
    local lockfile=migrations.lock
    local cmd=(make migrations)
    log_color '0;33' "Checking: ${cmd[*]}"
    "${cmd[@]}" >/dev/null  # don't output the diff twice
    git update-index -q --refresh
    if ! git diff --exit-code HEAD -- "$lockfile"; then
        # dirty
        log_color '0;31' "ERROR: Frozen migrations are inconsistent.  Did you run '${cmd[*]}'?"
        #git checkout "$lockfile"  # (don't) clean up
        return 1
    fi
    # clean
    log_color '0;32' "frozen migrations ok"
}


function log_color {
    local ccode="$1"
    shift
    local msg="$*"
    echo -e "\\033[${ccode}m${msg}\\033[0m" >&2
}


main "$@"
