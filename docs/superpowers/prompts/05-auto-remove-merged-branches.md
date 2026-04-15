# Auto-remove merged branches

https://dimagi.atlassian.net/browse/SAAS-19618

## Context

Right now, when a branch that is on staging is merged into master, that will (like all pushes) trigger a rebuild staging workflow run. However, that branch no longer needs to be in commcare-hq-staging.yml, and indeed will cause errors if the branch has been deleted, as is often the case. We will often see failures like

```
  [/home/runner/work/commcare-hq/commcare-hq] es/case-api-fields NOT FOUND
You must remove the following branches before rebuilding:
  [/home/runner/work/commcare-hq/commcare-hq] es/case-api-fields
    This branch may have been merged:
      commit 84580baa6bd45eb5b69d0a1a896dec369b5e1f80
      Merge: 93a3af1b7d2 541805a9e49
      Author: Ethan Soergel <esoergel@users.noreply.github.com>
      Date:   Tue Apr 14 12:54:39 2026 +0200
      
          Merge pull request #37519 from dimagi/es/case-api-fields
          
          Add fields/exclude params to Case API v2
You must fix the following merge conflicts before rebuilding:
```

which must be manually resolved by removing the identified branch from commcare-hq-staging.yml

## Problem

When a branch on staging is merged into master and deleted, the next rebuild fails because the branch no longer exists. This requires manual intervention to remove the branch from `commcare-hq-staging.yml`.

## Proposed solution

Automatically remove merged branches from `commcare-hq-staging.yml` before the rebuild runs.

1. For merges to commcare-hq master, check whether the merged branch is in commcare-hq-staging.yml.
2. If it's there, then instead of running the rebuild, trigger a new "remove branch" GHA workflow on staging-branches, with `{"file": "commcare-hq-staging.yml", "branch": branch}`
3. Exit with "neutral" status (or similar status that is neither failure nor success, as the central rebuildstaging run didn't happen at all.)

The new "remove branch" GHA workflow on staging-branches should check take two parameters, `file`, and `branch`, and remove the `branch` entry from file `file`.

## Out of scope

- Auto-triggering rebuilds on branch push (separate improvement)
- Slack notifications for rebuild failures (separate improvement)
- Deploy coordination (separate improvement)
