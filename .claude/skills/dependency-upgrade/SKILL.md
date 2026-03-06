---
name: dependency-upgrade
description: Investigate and upgrade a Python or JavaScript dependency, then open a PR with a safety assessment.
argument-hint: <package_name>
---

# Dependency Upgrade

Given a package name, investigate the upgrade, make the change, and open a PR.

## Input

`$ARGUMENTS` — the package name. Examples:

- `/dependency-upgrade pillow`
- `/dependency-upgrade dompurify`

## Step 1: Determine the ecosystem and current version

**Python:** Search `uv.lock` for the package name and note the pinned version.

**JavaScript:** Check `package.json`.

Note the current pinned version.

## Step 2: Find the latest version

**Python:**
```bash
curl -s https://pypi.org/pypi/<package>/json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['info']['version'])"
```

**JavaScript:**
```bash
npm view <package> version
```

## Step 3: Evaluate the target version

- **Skip brand new major releases** — if the latest version is a new major (e.g. `5.0.0` released within the last ~3 months), target the previous major's latest patch instead to allow time for bugs to surface.
- Otherwise, target the latest version.

## Step 4: Pull the changelog

Fetch the changelog between the current version and the target version. Try in order:

1. The package's GitHub releases page via `gh` or `WebFetch`
2. PyPI / npm for a changelog or release notes link
3. The project's `CHANGELOG.md` or `HISTORY.md` on GitHub

Note the URL where you found the changelog — you will include it in the PR.

Read the changelog for:
- **Breaking changes** — API removals, behavior changes, renamed options
- **Security fixes**
- **Bug fixes** relevant to how CommCare HQ uses the package

## Step 5: Assess how CommCare HQ uses the package

Search the codebase to understand actual usage. Cross-reference against the changelog findings. Consider:
- Is this a runtime dependency or a build/dev tool?
- Which features/APIs does HQ actually call?
- Do any breaking changes touch those call sites?

If breaking changes affect HQ's usage, make the necessary code changes alongside the version bump.

## Step 6: Make the upgrade

**Python** — update the version in each `requirements/*.txt` file that pins it. Keep the existing pin style (`==` stays `==`, `>=` stays `>=`). Do not run `pip install`.

**JavaScript** — update `package.json`, then run:
```bash
yarn upgrade <package>@<target_version>
```
Commit `yarn.lock` if present.

## Step 7: Commit and open a PR

Follow the version control instructions in `CLAUDE.md` (branch prefix, draft PR, PR template, etc.).

Branch name: `<prefix>/<package>/<target_version>`

Commit message: `Upgrade <package> to <target_version>`

PR title: `Upgrade <package> to <target_version>`

Fill in the PR template with your findings. The technical summary should include a link to the changelog. The safety story should explain why this upgrade is safe given HQ's actual usage. Omit the Migrations section. Check the rollback box. Add the `product/invisible` label.
