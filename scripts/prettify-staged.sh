#!/bin/bash

set -e

prettify() {
    FILES=$1
    echo "Formatting staged and uncommitted files:"
    ./node_modules/.bin/prettier --write $FILES
    echo
    echo "Remember to stage these files before committing."
}

# Get a list of staged files with appropriate extensions
STAGED_FILES=$(git diff --staged --name-only --diff-filter=d| grep -E "\.(html|css|scss|less)$")
if [ -z "$STAGED_FILES" ]; then
    echo "No staged files to format."
    exit 0
fi

prettify "$STAGED_FILES"
