#!/bin/bash
# Build one Redoc reference page per generated OpenAPI spec.
#
# Output goes to docs/api/dist/ and is NOT committed: deployed environments
# build static assets as a required step, and a local checkout can rebuild with
# `yarn openapi:docs`.
#
# The bundle is skipped deliberately -- it exists for machine consumers, and a
# single page covering every API is what the per-API pages replace.
set -euo pipefail

SPEC_DIR='docs/api/spec'
DIST_DIR='docs/api/dist'

mkdir -p "$DIST_DIR"
rm -f "$DIST_DIR"/*.html

shopt -s nullglob
specs=("$SPEC_DIR"/*.json)
shopt -u nullglob

if [ ${#specs[@]} -eq 0 ]; then
    echo "no OpenAPI specs found in $SPEC_DIR" >&2
    exit 1
fi

built=0
for spec in "${specs[@]}"; do
    slug="$(basename "$spec" .json)"
    if [ "$slug" = 'bundle' ]; then
        continue
    fi
    yarn redocly build-docs "$spec" -o "$DIST_DIR/$slug.html"
    built=$((built + 1))
done

if [ "$built" -eq 0 ]; then
    echo "no API reference pages were built from $SPEC_DIR" >&2
    exit 1
fi

echo "built $built API reference pages into $DIST_DIR"
