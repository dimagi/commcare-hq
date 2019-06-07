#!/usr/bin/env bash
set -e

# This is a dirty test. It can leave some files in a different state
# than they were when it started.
make requirements
git diff
git update-index -q --refresh
if git diff-index --quiet HEAD --; then
    # No changes
    echo "requirements ok"
else
    # Changes
    echo -e "\033[0;31mRequirements are inconsistent.  Did you run 'make requirements'?\033[0m"
    exit 1
fi
