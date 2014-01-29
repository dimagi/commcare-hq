#!/bin/bash

function git-submodule-list() {
    git submodule | sed 's/^+/ /' | cut -f3 -d' '
}

cp git-hooks/pre-commit.sh .git/hooks/pre-commit
git-submodule-list | xargs -n1 -I% cp git-hooks/pre-commit.sh .git/modules/%/hooks/pre-commit
