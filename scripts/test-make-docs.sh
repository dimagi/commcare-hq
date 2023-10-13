#!/bin/bash

# If the "Test commcare-hq docs" github action is failing, you're in the right
# place.
#
# You have two options:
#
# Download the make-docs-errors.log file that triggered the failure from the
# github actions artifacts to view newly introduced warnings/errors.
# --- OR ---
# Build docs locally on your branch to see what warnings/errors
# you have introduced. To do so, follow these instructions:
#
# 1) Install requirements/docs-requirements.txt ideally using pip-sync:
#   `pip-sync requirements/docs-requirements.txt`
# 2) Ensure a fresh docs build by deleting any previously generated build
#    `rm -rf docs/_build`
# 3) Using bash, run this script:
#    `bash test-make-docs.sh`
# 4) Inspect the terminal output or make-docs-errors.log (they are the same) to understand new warnings/errors:
#    `cat make-docs-errors.log`

WHITELIST_PATTERNS=(
    '^\s*$'  # ignore lines containing only whitespace
    'logger is being changed to' # ignore error when FIX_LOGGER_ERROR_OBFUSCATION is true
    'yacc table file version is out of date' # warning whenever building docs on a freshly created virtual environment
    # Only whitelist docs build warnings/errors when absolutely necessary
)

function main {
    # printf '%s|' - append a pipe character (|) to each commandline arg and write it to STDOUT
    # "${WHITELIST_PATTERNS[@]}" - expand the contents of Bash Array WHITELIST_PATTERNS as individual args
    # sed -E 's/\|$//' - remove a single trailing pipe character (|) from any lines on STDIN
    local whitelist=$(printf '%s|' "${WHITELIST_PATTERNS[@]}" | sed -E 's/\|$//')

    # make docs 2>&1 1>/dev/null - redirect STDERR to STDOUT, and then STDOUT to /dev/null
    # grep -Ev "(${whitelist})" - only match lines that do not match regex patterns of whitelisted items
    local log_file='./make-docs-errors.log'
    make docs 2>&1 1>/dev/null | grep -Ev "(${whitelist})" | tee $log_file

    # move docs build and log file to artifacts if running inside github action
    if [ -n "$GITHUB_ACTIONS" ]; then
        mkdir -p ./artifacts
        mv ./docs/_build/html ./artifacts/
        mv make-docs-errors.log ./artifacts/
        log_file='./artifacts/make-docs-errors.log'
    fi

    # fail if log file is not empty
    if [ -s $log_file ]; then
        return 1
    fi
}

main "$@"
