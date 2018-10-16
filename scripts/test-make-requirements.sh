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
    exit 1
fi
