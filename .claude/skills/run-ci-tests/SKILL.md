---
name: run-ci-tests
description: Kick off the commcare-hq tests GitHub Actions workflow on a branch. Use whenever the user asks to "run tests on CI", "trigger the test workflow", "run the GitHub Action tests", "kick off CI", or anything similar — with or without naming a branch. If no branch is specified, run it on the current branch.
---

# Run Tests Workflow

Triggers the `tests.yml` GitHub Actions workflow (`workflow_dispatch`) on a
branch and reports the resulting run URL.

## Steps

1. **Determine the branch.**
   - If the user named one, use it.
   - Otherwise: `git rev-parse --abbrev-ref HEAD`. If this returns `HEAD`,
     the user is on a detached commit — stop and ask which branch they
     mean.
   - If the resolved branch is `master`, stop and confirm with the user.
     The workflow already runs on PRs to master, so manual dispatches
     against it are usually a mistake.

2. **Verify the branch exists on the remote.**
   ```bash
   git ls-remote --heads origin <branch>
   ```
   If the output is empty, stop and tell the user the branch isn't pushed.
   Don't auto-push — pushing is a side effect the user should authorize.

3. **Warn if local is ahead of remote.** CI runs the remote ref, so any
   unpushed commits on the local branch won't be tested. Check:
   ```bash
   git rev-list --count origin/<branch>..<branch>
   ```
   If non-zero, mention it to the user before dispatching ("you have N
   unpushed commits — CI will run the remote tip"). Don't block; they may
   know.

4. **Dispatch the workflow.**
   ```bash
   gh workflow run tests.yml --ref <branch>
   ```

5. **Find and report the run.** The dispatch command doesn't return a run
   ID. `gh run list` only supports `--workflow` and `--limit` as filters
   (no `--branch` or `--event`), so include `headBranch` and `event` in
   the JSON output and filter with `--jq`:
   ```bash
   sleep 3
   gh run list --workflow=tests.yml --limit=5 \
     --json databaseId,url,status,createdAt,headBranch,event \
     --jq '[.[] | select(.headBranch=="<branch>" and .event=="workflow_dispatch")] | .[0]'
   ```
   Filtering by `workflow_dispatch` matters so a recent PR-triggered run
   on the same branch doesn't get reported by mistake. GitHub takes a few
   seconds to register the run; if the result is empty or `createdAt`
   looks stale, sleep a few more seconds and retry once. Then hand the
   URL to the user.

## Notes

- The workflow file is `.github/workflows/tests.yml`. It already declares
  `workflow_dispatch`, so no setup is needed to enable manual triggers.
- `gh` must be authenticated — if commands fail, suggest `gh auth status`.
- Don't poll the run to completion unless the user asks. The suite takes
  a long time; just return the URL.
