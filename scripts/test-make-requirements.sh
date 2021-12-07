#!/usr/bin/env bash
set -e

# source utils for logging functions log_group_{begin,end} and log_{success,fail}
source ./scripts/bash-utils.sh

log_group_begin "Check: make requirements"
trap log_group_end EXIT

make requirements
git --no-pager diff
git update-index -q --refresh
if ! git diff-index --quiet HEAD --; then
    # Changes
    log_fail "Requirements are inconsistent.  Did you run 'make requirements'?"
    git checkout requirements/  # clean up
    exit 1
fi
# No changes
log_success "requirements ok"
