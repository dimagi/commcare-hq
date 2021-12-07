#!/usr/bin/env bash
set -e


GROUP='0;33'    # gold
SUCCESS='0;32'  # green
FAIL='0;31'     # red


function main {
    local retcode=0
    check_makemigrations  || retcode=$(( $retcode + 1 ))
    check_migrations_list || retcode=$(( $retcode + 1 ))
    trap - RETURN  # traps propogate up, clear the RETURN trap
    return $retcode
}


function check_makemigrations {
    # check makemigrations
    local cmd=(./manage.py makemigrations)
    log_group "${cmd[*]}"
    trap 'echo "::endgroup::"' RETURN
    if ! "${cmd[@]}" --noinput --check; then
        # Changes
        log_fail "Migrations are missing.  Did you run '${cmd[*]}'?"
        return 1
    fi
    # No changes
    log_success "makemigrations ok"
}


function check_migrations_list {
    # ensure migrations lockfile is consistent with actual migrations list
    local lockfile=migrations.lock
    local cmd=(make migrations.lock)
    log_group "${cmd[*]}"
    trap 'echo "::endgroup::"' RETURN
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
}


function log_group {
    local group_info="$*"
    # use GitHub workflow grouping log lines
    # see: https://docs.github.com/en/actions/learn-github-actions/workflow-commands-for-github-actions#grouping-log-lines
    echo "::group::Check $group_info"
    log_color "$GROUP" "Checking $group_info"
}


function log_success {
    log_color "$SUCCESS" "$@"
}


function log_fail {
    log_color "$FAIL" "ERROR:" "$@"
}


function log_color {
    local ccode="$1"
    shift
    local msg="$*"
    echo -e "\\033[${ccode}m${msg}\\033[0m"
}


main "$@"
