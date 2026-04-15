# Auto-Remove Merged Branches Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically remove merged branches from the staging config so that staging rebuilds don't fail when a branch has been deleted after merge.

**Architecture:** When a PR is merged to master in commcare-hq, the rebuild-staging workflow detects whether the merged branch is in the staging config. If it is, it triggers a remove-branch workflow on the staging-branches repo instead of rebuilding. The removal commits to main, which triggers the existing rebuild pipeline with the branch removed.

**Tech Stack:** GitHub Actions, bash, grep (PCRE), GitHub App tokens for cross-repo auth

**Spec:** `docs/superpowers/specs/2026-04-14-auto-remove-merged-branches-design.md`

**Prerequisites:** The GitHub App behind `STAGING_BRANCHES_APP_ID` / `STAGING_BRANCHES_APP_PRIVATE_KEY` must be installed on the staging-branches repo, and those secrets must be added to commcare-hq's repo secrets. This is a manual step outside the scope of the code changes.

---

### Task 1: Create remove-branch.yml in staging-branches

**Files:**
- Create: `staging-branches/.github/workflows/remove-branch.yml`

- [ ] **Step 1: Write the workflow file**

```yaml
name: Remove branch from staging config

on:
  workflow_dispatch:
    inputs:
      file:
        description: 'Staging config file (e.g. commcare-hq-staging.yml)'
        required: true
        type: string
      branch:
        description: 'Branch name to remove'
        required: true
        type: string

jobs:
  remove-branch:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v6

    - name: Remove branch from config
      id: remove
      env:
        FILE: ${{ inputs.file }}
        BRANCH: ${{ inputs.branch }}
      run: |
        if [ ! -f "$FILE" ]; then
          echo "::error::File '$FILE' not found"
          exit 1
        fi

        # Remove standalone branch entry (not +-joined conflict resolution branches).
        # Matches lines like "    - branch-name  # optional comment"
        # but not "    - foo+branch-name+bar"
        grep -vP "^\s*-\s+\Q${BRANCH}\E(\s|$)" "$FILE" > "${FILE}.tmp"
        mv "${FILE}.tmp" "$FILE"

        if git diff --quiet -- "$FILE"; then
          echo "::notice::Branch '$BRANCH' not found in $FILE, nothing to remove"
        else
          echo "changed=true" >> "$GITHUB_OUTPUT"
          echo "Removed branch '$BRANCH' from $FILE"
          git diff -- "$FILE"
        fi

    - name: Commit and push
      if: steps.remove.outputs.changed == 'true'
      env:
        FILE: ${{ inputs.file }}
        BRANCH: ${{ inputs.branch }}
      run: |
        git config user.name "GitHub Actions"
        git config user.email "actions@github.com"
        git add "$FILE"
        git commit -m "Remove merged branch \`$BRANCH\` from $FILE"
        git push
```

- [ ] **Step 2: Verify the grep pattern works against real staging config data**

Create a test file from the real config and verify the pattern matches standalone entries but not `+`-joined entries:

```bash
cd /Users/danielroberts/dimagi/staging-branches

# Should match (standalone entry) — exit code 0
echo '    - es/case-api-fields  # Ethan Feb 18' | grep -P '^\s*-\s+\Q'"es/case-api-fields"'\E(\s|$)'

# Should NOT match (+-joined) — exit code 1
echo '    - riese/query_builder_claude_v3+es/config-cs-endpoints+gh/demo-case-pillow' | grep -P '^\s*-\s+\Q'"es/config-cs-endpoints"'\E(\s|$)'

# Should match (no comment, end of line)
echo '    - gh/repeaters/disable-check' | grep -P '^\s*-\s+\Q'"gh/repeaters/disable-check"'\E(\s|$)'

# Verify grep -v removes only the target line from real config
grep -vP '^\s*-\s+\Q'"gh/repeaters/disable-check"'\E(\s|$)' commcare-hq-staging.yml | diff commcare-hq-staging.yml -
```

Expected: first and third commands succeed (exit 0), second fails (exit 1), fourth shows only the removed line in the diff.

- [ ] **Step 3: Commit**

```bash
cd /Users/danielroberts/dimagi/staging-branches
git checkout -b dmr/auto-remove-merged-branches
git add .github/workflows/remove-branch.yml
git commit -m "Add workflow to remove merged branches from staging config

When a branch on staging is merged to master, commcare-hq's rebuild-staging
workflow will trigger this to remove the branch from the config file.
The resulting push to main triggers the existing rebuild pipeline.

SAAS-19618"
```

---

### Task 2: Modify rebuild-staging.yml in commcare-hq

**Files:**
- Modify: `commcare-hq/.github/workflows/rebuild-staging.yml`

- [ ] **Step 1: Verify the merge commit regex works against real commit messages**

`github.event.head_commit.message` includes the full multi-line commit message. The regex uses `$` which matches end of string in bash, not end of line. So we extract the first line before matching.

```bash
cd /Users/danielroberts/dimagi/commcare-hq

# Test with a multi-line merge commit message (realistic format)
MSG="Merge pull request #37519 from dimagi/es/case-api-fields

Add fields/exclude params to Case API v2"
FIRST_LINE="${MSG%%$'\n'*}"
if [[ "$FIRST_LINE" =~ ^Merge\ pull\ request\ \#[0-9]+\ from\ [^/]+/(.+)$ ]]; then
  echo "Matched: '${BASH_REMATCH[1]}'"
else
  echo "No match"
fi
# Expected: Matched: 'es/case-api-fields'

# Test with a non-merge commit message
MSG="Fix typo in readme"
FIRST_LINE="${MSG%%$'\n'*}"
if [[ "$FIRST_LINE" =~ ^Merge\ pull\ request\ \#[0-9]+\ from\ [^/]+/(.+)$ ]]; then
  echo "Matched: '${BASH_REMATCH[1]}'"
else
  echo "No match"
fi
# Expected: No match
```

- [ ] **Step 2: Update the workflow file**

Replace the full contents of `.github/workflows/rebuild-staging.yml` with:

```yaml
name: Rebuild staging branch
on:
  workflow_dispatch:
  push:
    branches:
      - '**'

concurrency:
  group: rebuild-staging
  cancel-in-progress: false

jobs:
  check-branch:
    runs-on: ubuntu-latest
    outputs:
      should-rebuild: >-
        ${{ github.event_name == 'workflow_dispatch'
            || (steps.check.outputs.found == 'true'
                && steps.check-merged.outputs.is-merged-staging-branch != 'true') }}
      is-merged-staging-branch: >-
        ${{ steps.check-merged.outputs.is-merged-staging-branch }}
      merged-branch: >-
        ${{ steps.check-merged.outputs.merged-branch }}
    steps:
    - name: Check if branch is in staging config
      id: check
      if: github.event_name == 'push'
      env:
        BRANCH: ${{ github.ref_name }}
      run: |
        curl -sf https://raw.githubusercontent.com/dimagi/staging-branches/main/commcare-hq-staging.yml \
          -o staging.yml
        if grep -qF "$BRANCH" staging.yml; then
          echo "found=true" >> "$GITHUB_OUTPUT"
        else
          echo "Branch '$BRANCH' not found in staging config, skipping rebuild"
        fi

    - name: Check if push to master merged a staging branch
      id: check-merged
      if: github.event_name == 'push' && github.ref_name == 'master'
      env:
        COMMIT_MSG: ${{ github.event.head_commit.message }}
      run: |
        # Extract branch name from the first line of the merge commit message
        # Format: "Merge pull request #NNN from owner/branch-name"
        FIRST_LINE="${COMMIT_MSG%%$'\n'*}"
        if [[ "$FIRST_LINE" =~ ^Merge\ pull\ request\ \#[0-9]+\ from\ [^/]+/(.+)$ ]]; then
          MERGED_BRANCH="${BASH_REMATCH[1]}"
          echo "Detected merged branch: $MERGED_BRANCH"

          # Check if this branch is a standalone entry in the staging config
          # (not part of a +-joined conflict resolution branch)
          if grep -qP "^\s*-\s+\Q${MERGED_BRANCH}\E(\s|$)" staging.yml; then
            echo "is-merged-staging-branch=true" >> "$GITHUB_OUTPUT"
            echo "merged-branch=$MERGED_BRANCH" >> "$GITHUB_OUTPUT"
            echo "Branch '$MERGED_BRANCH' found in staging config, will trigger removal"
          else
            echo "Merged branch '$MERGED_BRANCH' not in staging config as standalone entry"
          fi
        else
          echo "Not a merge commit, skipping merged branch check"
        fi

  remove-merged-branch:
    needs: check-branch
    if: needs.check-branch.outputs.is-merged-staging-branch == 'true'
    runs-on: ubuntu-latest
    steps:
    - name: Generate GitHub App token
      id: app-token
      uses: actions/create-github-app-token@v1
      with:
        app-id: ${{ secrets.STAGING_BRANCHES_APP_ID }}
        private-key: ${{ secrets.STAGING_BRANCHES_APP_PRIVATE_KEY }}
        owner: dimagi
        repositories: staging-branches

    - name: Trigger branch removal
      env:
        GH_TOKEN: ${{ steps.app-token.outputs.token }}
        BRANCH: ${{ needs.check-branch.outputs.merged-branch }}
      run: |
        echo "Triggering removal of branch '$BRANCH' from commcare-hq-staging.yml"
        gh workflow run remove-branch.yml \
          --repo dimagi/staging-branches \
          -f file=commcare-hq-staging.yml \
          -f branch="$BRANCH"

  rebuild-staging:
    needs: check-branch
    if: needs.check-branch.outputs.should-rebuild == 'true'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: write
    steps:
    - uses: actions/checkout@v6
      with:
        ref: master
        # Full history needed for branch manipulation
        fetch-depth: 0
    - uses: astral-sh/setup-uv@v7
    - name: Install git-build-branch
      run: uv tool install git-build-branch
    - name: Configure git
      run: |
        git config user.name "GitHub Actions"
        git config user.email "actions@github.com"
    - name: Rebuild staging
      run: ./scripts/rebuildstaging
```

- [ ] **Step 3: Verify no YAML syntax errors**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/rebuild-staging.yml'))"
```

Expected: no output (valid YAML).

- [ ] **Step 4: Commit**

```bash
cd /Users/danielroberts/dimagi/commcare-hq
git checkout -b dmr/auto-remove-merged-branches
git add .github/workflows/rebuild-staging.yml
git commit -m "Auto-remove merged branches from staging config

When a PR merges a branch that is in the staging config, trigger
the remove-branch workflow on staging-branches instead of rebuilding.
The removal then triggers a clean rebuild via the existing pipeline.

SAAS-19618"
```

---

### Task 3: Create draft PRs

**Files:** None (git/GitHub operations only)

- [ ] **Step 1: Push and create PR for staging-branches**

```bash
cd /Users/danielroberts/dimagi/staging-branches
git push -u origin dmr/auto-remove-merged-branches
gh pr create --draft \
  --title "Add workflow to auto-remove merged branches from staging config" \
  --label "DON'T REVIEW YET" \
  --body "$(cat <<'EOF'
<!-- PR template content -->
EOF
)"
```

- [ ] **Step 2: Push and create PR for commcare-hq**

```bash
cd /Users/danielroberts/dimagi/commcare-hq
git push -u origin dmr/auto-remove-merged-branches
gh pr create --draft \
  --title "Auto-remove merged branches from staging config" \
  --label "DON'T REVIEW YET" \
  --body "$(cat <<'EOF'
<!-- PR template content -->
EOF
)"
```

Note: The staging-branches PR must be merged first so that the `remove-branch.yml` workflow exists when commcare-hq triggers it. The GitHub App secrets (`STAGING_BRANCHES_APP_ID`, `STAGING_BRANCHES_APP_PRIVATE_KEY`) must also be configured in commcare-hq's repo settings before the commcare-hq PR is merged.
