#!/usr/bin/env bash
set -e

echo "::group::make requirements"
trap 'echo "::endgroup::"' EXIT

make requirements
git --no-pager diff
git update-index -q --refresh
if git diff-index --quiet HEAD --; then
    # No changes
    echo "requirements ok"
else
    # Changes
    echo -e "\033[0;31mRequirements are inconsistent.  Did you run 'make requirements'?\033[0m"
    git checkout requirements/  # clean up
    exit 1
fi
