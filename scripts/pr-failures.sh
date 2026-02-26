#!/bin/bash
# Show test failures for a GitHub Actions CI run on a PR.
# Usage: scripts/pr-failures.sh [<pr_number> [<repo>]]
# If no PR number is given, uses the current branch's open PR.
# If no repo is given, uses the current directory's repo.

set -euo pipefail

if ! command -v gh &>/dev/null; then
    echo "Error: 'gh' (GitHub CLI) is not installed." >&2
    echo "Install it from https://cli.github.com/" >&2
    exit 1
fi

PR=${1:-}
REPO=${2:-$(gh repo view --json nameWithOwner -q ".nameWithOwner")}

gh_exit=0
if [[ -n "$PR" ]]; then
    FAILED=$(gh pr checks "$PR" --repo "$REPO" | awk -F'\t' '$2 == "fail"') || gh_exit=$?
else
    FAILED=$(gh pr checks | awk -F'\t' '$2 == "fail"') || gh_exit=$?
fi

# Non-zero exit + no tab-separated output = real gh error (already printed to stderr)
if [[ $gh_exit -ne 0 && -z "$FAILED" ]]; then
    exit 1
fi

if [[ -z "$FAILED" ]]; then
    echo "No failed checks${PR:+ for PR #$PR}."
    exit 0
fi

echo "Failed checks:"
echo "$FAILED" | awk -F'\t' '{print "  " $1}'

# Extract run ID + job ID pairs from GitHub Actions URLs (runs/<id>/job/<id>)
# Format: "<run_id> <job_id>" per line
RUN_JOB_PAIRS=$(echo "$FAILED" | grep -oE 'runs/[0-9]+/job/[0-9]+' \
    | sed 's|runs/\([0-9]*\)/job/\([0-9]*\)|\1 \2|' | sort -u) || true

if [[ -z "$RUN_JOB_PAIRS" ]]; then
    echo ""
    echo "Could not extract run/job IDs. Check URLs manually:"
    echo "$FAILED" | awk '{print "  " $NF}'
    exit 1
fi

echo ""
echo "Failures:"
LOCAL_HEAD=$(git rev-parse HEAD 2>/dev/null || true)
SEEN_RUNS=""
while IFS=' ' read -r RUN_ID JOB_ID; do
    if [[ ! " $SEEN_RUNS " =~ " $RUN_ID " ]]; then
        SEEN_RUNS="$SEEN_RUNS $RUN_ID"
        RUN_SHA=$(gh api "repos/$REPO/actions/runs/$RUN_ID" --jq '.head_sha' 2>/dev/null || true)
        if [[ -n "$RUN_SHA" && -n "$LOCAL_HEAD" && "$RUN_SHA" != "$LOCAL_HEAD" ]]; then
            echo "⚠️  This failure is from commit ${RUN_SHA:0:7} — your current HEAD is ${LOCAL_HEAD:0:7}. The failure may already be fixed."
        fi
    fi
    gh api "repos/$REPO/actions/jobs/$JOB_ID/logs" 2>&1 \
        | sed 's/^[0-9T:.-]*Z //' \
        | grep -E "(^FAILED |##\[error\])" || true
done <<< "$RUN_JOB_PAIRS"
