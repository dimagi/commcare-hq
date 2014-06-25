#!/bin/bash

function usage()
{
    cat << EOF
usage: $0 options

This script installs CommCare HQ's default git hooks on all submodules

OPTIONS:
   -h      Show this message
   -f      don't ask before overwriting your current git hooks
   -r      remove existing hooks but do not add the new ones
EOF
}

OPT='-i'
FUNC='copy_hooks'

while getopts "hfr" OPTION
do
    case $OPTION in
        h)
            usage
            exit
            ;;
        f)
            OPT='-f'
            ;;
        r)
            FUNC='remove_hooks'
            ;;
        ?)
            usage
            exit 1
            ;;
    esac
done

function copy_hooks() {
    hook=$1
    base_path=$2
    cp $OPT git-hooks/$hook.sh $base_path/hooks/$hook
}

function remove_hooks() {
    hook=$1
    base_path=$2
    rm $OPT $base_path/hooks/$hook
}

function git-submodule-list() {
    git submodule | sed 's/^+/ /' | cut -f3 -d' '
}

for hook in 'pre-commit' 'post-checkout'
do

    ${FUNC} $hook '.git'
    for submodule in $(git-submodule-list)
    do
        ${FUNC} $hook ".git/modules/$submodule"
    done
done
