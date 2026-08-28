#!/bin/bash
# Verify the committed OpenAPI artifacts in docs/api/openapi/dist/ match the
# source spec. Regenerating into a temp dir and diffing means a spec change
# cannot merge without its artifacts being refreshed.
#
# If this fails: run `yarn openapi:bundle && yarn openapi:docs` and commit.
set -euo pipefail

DIST='docs/api/openapi/dist'
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/openapi"
npx redocly bundle --config docs/api/openapi/redocly.yaml commcare \
    -o "$TMP/openapi.bundled.yaml"
npx redocly build-docs --config docs/api/openapi/redocly.yaml commcare \
    -o "$TMP/openapi/index.html"

status=0
for file in openapi.bundled.yaml openapi/index.html; do
    if ! diff -q "$DIST/$file" "$TMP/$file" >/dev/null 2>&1; then
        echo "ERROR: $DIST/$file is stale."
        status=1
    fi
done

if [ "$status" -ne 0 ]; then
    echo
    echo 'Regenerate with: yarn openapi:bundle && yarn openapi:docs'
fi
exit "$status"
