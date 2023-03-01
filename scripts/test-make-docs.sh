#!/bin/bash

# If the "Test commcare-hq docs" github action is failing, you're in the right
# place.
#
# You have two options:
#
# Download the log file that triggered the failure from the
# github actions artifacts to view newly introduced warnings/errors.
# --- OR ---
# Build docs locally to see what warnings/errors
# you have introduced with your changes. To do so, follow these instructions:
#
# 1) Install requirements/docs-requirements.txt ideally using pip-sync:
#   `pip-sync requirements/docs-requirements.txt`
# 2) Using bash, run this script:
#    `bash test-make-docs.sh`
# 3) Inspect the make-docs-errors.log to understand new warnings/errors:
#    `cat ./artifacts/make-docs-errors.log`

WHITELIST_PATTERNS=(
    '^\s*$'  # ignore lines containing only whitespace
    'logger is being changed to' # ignore error when FIX_LOGGER_ERROR_OBFUSCATION is true
    # Only whitelist docs build warnings/errors when absolutely necessary
)

function main {
    # printf '%s|' - append a pipe character (|) to each commandline arg and write it to STDOUT
    # "${WHITELIST_PATTERNS[@]}" - expand the contents of Bash Array WHITELIST_PATTERNS as individual args
    # sed -E 's/\|$//' - remove a single trailing pipe character (|) from any lines on STDIN
    local whitelist=$(printf '%s|' "${WHITELIST_PATTERNS[@]}" | sed -E 's/\|$//')

    mkdir -p ./artifacts

    # make docs 2>&1 1>/dev/null - redirect STDERR to STDOUT, and then STDOUT to /dev/null
    # grep -Ev "(${whitelist})" - only match lines that do not match regex patterns of whitelisted items
    make docs 2>&1 1>/dev/null | grep -Ev "(${whitelist})" | tee ./artifacts/make-docs-errors.log

    cp -r ./docs/_build/html ./artifacts/

    # fail if error log file is not empty
    if [ -s "./artifacts/make-docs-errors.log" ]; then
        return 1
    fi
}

main "$@"
