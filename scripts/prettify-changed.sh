#!/bin/bash

get_changed() {
    # Get a list of changed and committed files with appropriate extensions
    git diff master...HEAD --name-only --diff-filter=d | grep -E "\.(html|css|scss|less)$"
}

prettify() {
    FILES=$1
    echo "Formatting files changed on this branch:"
    ./node_modules/.bin/prettier --write "$FILES"
    echo
}

CHANGED_FILES=$(get_changed) || { echo "No changed files found to format." && exit 1; }
prettify "$CHANGED_FILES" || { echo "Oops! Did you remember to run yarn install?" && exit 1; }

echo "Remember to commit these changes."
