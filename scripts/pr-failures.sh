#!/bin/bash
# Show test failures for a GitHub Actions CI run on a PR.
# Usage: scripts/pr-failures.sh <pr_number>

set -euo pipefail

if ! command -v gh &>/dev/null; then
    echo "Error: 'gh' (GitHub CLI) is not installed." >&2
    echo "Install it from https://cli.github.com/" >&2
    exit 1
fi

if ! gh auth status &>/dev/null; then
    echo "Error: 'gh' is not authenticated. Run 'gh auth login' first." >&2
    exit 1
fi

PR=${1:?Usage: scripts/pr-failures.sh <pr_number>}
REPO="dimagi/commcare-hq"

FAILED=$(gh pr checks "$PR" --repo "$REPO" 2>/dev/null | awk -F'\t' '$2 == "fail"') || true

if [[ -z "$FAILED" ]]; then
    echo "No failed checks for PR #$PR."
    exit 0
fi

echo "Failed checks:"
echo "$FAILED" | awk -F'\t' '{print "  " $1}'

# Extract unique run IDs from GitHub Actions URLs (runs/<id>/job/<id>)
RUN_IDS=$(echo "$FAILED" | grep -oE 'runs/[0-9]+' | grep -oE '[0-9]+' | sort -u) || true

if [[ -z "$RUN_IDS" ]]; then
    echo ""
    echo "Could not extract run IDs. Check URLs manually:"
    echo "$FAILED" | awk '{print "  " $NF}'
    exit 1
fi

echo ""
echo "Failures:"
for RUN_ID in $RUN_IDS; do
    gh run view "$RUN_ID" --repo "$REPO" --log-failed 2>&1 \
        | grep -E "(FAILED |short test summary info|\[.*\] ERROR:)" \
        | sed 's/^[^\t]*\t[^\t]*\t[0-9T:.-]*Z //' || true
done
