#!/bin/bash
# Trigger the tests.yml workflow for the current branch and print the run URL.
# Usage: scripts/run-tests-in-github-actions.sh

set -euo pipefail

if ! command -v gh &>/dev/null; then
    echo "Error: 'gh' (GitHub CLI) is not installed." >&2
    echo "Install it from https://cli.github.com/" >&2
    exit 1
fi

branch=$(git branch --show-current)
if [[ -z $branch ]]; then
    echo "Error: not on a branch (detached HEAD?)." >&2
    exit 1
fi

echo "Triggering tests.yml on $branch..."
gh workflow run tests.yml --ref "$branch" >/dev/null

max_attempts=8
for ((i = 0; i < max_attempts; i++)); do
    sleep 2
    url=$(gh run list --workflow=tests.yml --limit 5 --json url,headBranch \
        -q "[.[] | select(.headBranch==\"$branch\")][0].url" || true)
    if [[ -n ${url:-} ]]; then
        echo "View the run at: $url"
        exit 0
    fi
done

echo "Workflow run not found yet — check 'gh run list --branch $branch'." >&2
exit 1
