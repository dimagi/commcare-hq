#!/usr/bin/env bash
set -e

# source utils for logging functions log_group_{begin,end} and log_{success,fail}
source ./scripts/bash-utils.sh

log_group_begin "Check: make serializer-pickle-files.lock"

make serializer-pickle-files.lock
git --no-pager diff
git update-index -q --refresh
if ! git diff-index --quiet HEAD --; then
    # Changes
    log_fail "Did you add a new usage of @task(serializer='pickle')? Please use the default serializer (json) instead."
    log_fail 'If you removed @task(serializer='pickle') usages, make sure to run `make serializer-pickle-files.lock`'
    log_fail 'and commit `serializer-pickle-files.lock`'
    git checkout serializer-pickle-files.lock  # clean up
    exit 1
fi
# No changes
log_success "serializer-pickle-files.lock ok"
log_group_end  # only log group end on success (prevents group collapse on failure)
