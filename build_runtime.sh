#!/usr/bin/env bash

find . \( \
    -name "*.py" -or \
    -name "*.json" -or \
    -name '*.yml' -or \
    -name '*.yaml' -or \
    -path '*/templates/*' -or \
    -path './staticfiles/CACHE/manifest.json' \
    \) \( \
    -not -path "./.git/*" \
    -not -path "./build/*" \
    -not -path "./deployment/*" \
    -not -path "./bower_components/*" \
    -not -path "./node_modules/*" \
    \) | cpio -pdamv build/runtime