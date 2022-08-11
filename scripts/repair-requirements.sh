#!/usr/bin/env bash

set -e

PIN_IN=./requirements/base-requirements.in


function main {
    local remote branch trap_cmd
    local pin_in="$PIN_IN"
    local pins=()
    while [ $# -gt 0 ]; do
        case "$1" in
            -h|--help)
                usage
                return 0
                ;;
            -i|--inventory-file)
                shift
                pin_in="$1"
                ;;
            -p|--push-to)
                shift
                branch=$(git_verify_remote_branch "$1")
                remote=$(echo "$branch" | awk -F/ '{print $1}')
                branch=$(echo "$branch" | tail -c +$(( ${#remote} + 2 )))
                ;;
            *)
                pins+=( "$1" )
                ;;
        esac
        shift
    done

    # verify base requirements file exists
    if ! [ -f "$pin_in" ]; then
        logmsg ERROR "invalid requirements base file: $pin_in"
        return 1
    fi

    # don't run if no pins are provided
    if [ ${#pins[@]} -lt 1 ]; then
        usage "If you don't need to pin packages, simply run 'make requirements' instead."
        return 1
    fi

    # checkout remote if specified
    if [ -n "$branch" ]; then
        trap_cmd=$(git_switch_to_remote_tracker "$remote" "$branch")
        trap "$trap_cmd" RETURN
    fi

    # repair the requirements files
    put_them_back "$pin_in" "${pins[@]}"

    # push changes if specified
    if [ -n "$branch" ]; then
        local requires_dir=$(dirname "$pin_in")
        git_add_commit_and_push "$requires_dir" "$remote" "$branch" "${pins[@]}"
    fi
}


function put_them_back {
    local pin_in="$1"; shift
    local pins=( "$@" )
    local original=$(cat "$pin_in")

    # append hard pins in the PIN_IN requirements file
    printf '%s\n' "${pins[@]}" >> "$pin_in"

    # build
    logmsg INFO "making requirements with pin(s)"
    make requirements >/dev/null 2>&1
    # remove the hard pins
    echo "$original" > "$pin_in"

    # rebuild
    logmsg INFO "making requirements without pin(s)"
    make requirements >/dev/null 2>&1
}


function git_switch_to_remote_tracker {
    local remote="$1"
    local branch="$2"
    local return_to nuke_this

    if git_dirty; then
        logmsg ERROR "Refusing to operate on a dirty working directory/index."
        return 1
    fi

    # get the current ref of HEAD
    return_to=$(git rev-parse --abbrev-ref --symbolic-full-name HEAD)
    if [ "$return_to" == HEAD ]; then
        # detached head, return to the SHA1
        return_to=$(git rev-parse HEAD)
    fi

    # trap command to "undo" what this function "does"
    return_to=$(printf '%q' "$return_to")
    nuke_this=$(printf '%q' "$branch")
    echo "git_do checkout $return_to && git_do branch -D $nuke_this"

    # do what we're here to do
    git_do checkout -b "$branch" "${remote}/${branch}"
}


function git_add_commit_and_push {
    local add_dir="$1"
    local remote="$2"
    local branch="$3"
    shift 3
    local pins=( "$@" )

    # diff, for visibility
    git_do --no-pager diff --no-function-context -U0 "$add_dir"

    # add
    git_do add "$add_dir"

    # commit
    {
        echo -e 'Rebuild broken requirements by pinning package(s)\n';
        printf -- '- %s\n' "${pins[@]}"
    } | git_do commit -F -

    # push
    git_do push "$remote" "${branch}:${branch}"
    logmsg INFO "Done, returning to previous ref"
}


function git_do {
    logmsg INFO "$ git $*"
    git "$@"
}


function git_dirty {
    ! (git diff --exit-code && git diff --cached --exit-code) >/dev/null
}


function git_verify_remote_branch {
    local branch="$1"
    # verify this is a valid remote branch
    if ! git branch -r | grep -E "^\\s*${branch}$" >/dev/null; then
        usage "Invalid remote branch: $branch"
        logmsg '' "Use the full remote ref name (for example:" \
            "origin/dependabot/pip/requirements/stripe-4.0.2) and" \
            "ensure it is fetched."
        return 1
    fi
    echo "$branch"
}


function logmsg {
    local level_name="$1"; shift
    local msg="$*"
    if [ -n "$level_name" ]; then
        level_name="${level_name}: "
    fi
    echo "${level_name}${msg}" >&2
}


function usage {
    local script=$(basename "$0")
    local msg="$*"
    logmsg USAGE "$script [-h|--help] [-i|--inventory-file FILE=${PIN_IN}] [-p|--push-to BRANCH] PIN [PIN [...]]"
    if [ -n "$msg" ]; then
        logmsg ERROR "$msg"
    fi
}


main "$@"
