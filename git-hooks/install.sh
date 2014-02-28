#!/bin/bash

function usage()
{
    cat << EOF
usage: $0 options

This script installs CommCare HQ's default git hooks on all submodules

OPTIONS:
   -h      Show this message
   -f      don't ask before overwriting your current git hooks
EOF
}

CP_OPT='-i'

while getopts "hf" OPTION
do
    case $OPTION in
        h)
            usage
            exit
            ;;
        f)
            CP_OPT='-f'
            ;;
        ?)
            usage
            exit 1
            ;;
    esac
done


function git-submodule-list() {
    git submodule | sed 's/^+/ /' | cut -f3 -d' '
}

for hook in 'pre-commit' 'post-checkout'
do

    cp git-hooks/$hook.sh .git/hooks/$hook
    for submodule in $(git-submodule-list)
    do
        cp $CP_OPT git-hooks/$hook.sh .git/modules/$submodule/hooks/$hook
    done
done
