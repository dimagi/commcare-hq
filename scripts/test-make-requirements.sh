#!/usr/bin/env bash
set -e

# 19.3.1 causes locally reproduceable test failure
# todo: remove this line once that's no longer a problem
pip install 'pip<19.3.0'

make requirements
git --no-pager diff
git update-index -q --refresh
if git diff-index --quiet HEAD --; then
    # No changes
    echo "requirements ok"
else
    # Changes
    echo -e "\033[0;31mRequirements are inconsistent.  Did you run 'make requirements'?\033[0m"
    git checkout requirements/ requirements-python3/  # clean up
    exit 1
fi
