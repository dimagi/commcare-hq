#!/usr/bin/env bash
set -e

make requirements
git diff
git update-index -q --refresh
if git diff-index --quiet HEAD --; then
    # No changes
    echo "requirements ok"
else
    # Changes
    echo -e "\033[0;31mRequirements are inconsistent.  Did you run 'make requirements'?\033[0m"
    git checkout requirements/ requirements-py3/  # clean up
    exit 1
fi
