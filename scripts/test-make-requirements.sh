#!/usr/bin/env bash
set -e

pip install pip-tools
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
