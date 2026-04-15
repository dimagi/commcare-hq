# Auto-remove merged branches from staging config

SAAS-19618: https://dimagi.atlassian.net/browse/SAAS-19618

## Problem

When a branch on staging is merged into master and deleted, the next staging
rebuild fails because the branch no longer exists. This requires manual
intervention to remove the branch from `commcare-hq-staging.yml` in the
staging-branches repo.

## Solution

Automatically detect when a merged-to-master branch is in the staging config,
and trigger its removal before the next rebuild.

## Repos involved

- **commcare-hq** — modify `.github/workflows/rebuild-staging.yml`
- **staging-branches** — add `.github/workflows/remove-branch.yml`

## Design

### commcare-hq: rebuild-staging.yml changes

The `check-branch` job gains new logic for pushes to `master`:

1. Parse `github.event.head_commit.message` with the regex
   `Merge pull request #[0-9]+ from [^/]+/(.+)` to extract the merged branch
   name.
2. If no match (not a PR merge commit), fall through to existing rebuild
   logic.
3. If a match, fetch `commcare-hq-staging.yml` from staging-branches and check
   if the branch appears as a standalone entry (not part of `+`-joined conflict
   resolution branches).
4. If listed, set `is-merged-staging-branch=true` and `should-rebuild=false`.
5. If not listed, fall through to existing rebuild logic (pushes to master
   still trigger rebuilds via the `trunk: master` grep match).

New outputs from `check-branch`:

- `is-merged-staging-branch` — true when a staging branch was just merged
- `merged-branch` — the extracted branch name

New job `remove-merged-branch`:

- Runs when `is-merged-staging-branch == 'true'`
- Generates a GitHub App token using `actions/create-github-app-token@v1`
  with `STAGING_BRANCHES_APP_ID` / `STAGING_BRANCHES_APP_PRIVATE_KEY`, scoped
  to `dimagi/staging-branches`
- Triggers `remove-branch.yml` on `dimagi/staging-branches` via
  `gh workflow run`, passing inputs `file=commcare-hq-staging.yml` and
  `branch=<merged-branch>`

The existing `rebuild-staging` job is unchanged, still gated on
`should-rebuild == 'true'`, which now excludes the merged-staging-branch case.

### staging-branches: new remove-branch.yml workflow

Triggered by `workflow_dispatch` with two inputs:

- `file` — the staging config filename (e.g. `commcare-hq-staging.yml`)
- `branch` — the branch name to remove

Steps:

1. Check out the staging-branches repo.
2. Remove the line matching `- <branch>` (with optional trailing comment) from
   the specified file. Only exact standalone entries are removed, not
   `+`-joined conflict resolution branches that reference the branch.
3. Commit with message like "Remove merged branch `<branch>` from `<file>`".
4. Push to `main`.

The push to `main` modifying the staging config file triggers the existing
`trigger-commcare-hq-rebuild.yml`, which dispatches a rebuild on commcare-hq
with the branch removed.

### Auth

The same GitHub App used by staging-branches (`STAGING_BRANCHES_APP_ID` /
`STAGING_BRANCHES_APP_PRIVATE_KEY`) will have its credentials added to
commcare-hq's repo secrets, scoped to the staging-branches repo.

### Exit status

When a staging branch is merged, the `rebuild-staging` job is skipped (its
`if` condition is false) and `remove-merged-branch` runs successfully. The
overall workflow shows as successful with the rebuild job skipped.

## Out of scope

- Removal of `+`-joined conflict resolution branches (manually managed)
- Auto-triggering rebuilds on branch push (separate improvement)
- Slack notifications for rebuild failures (separate improvement)
- Deploy coordination (separate improvement)
