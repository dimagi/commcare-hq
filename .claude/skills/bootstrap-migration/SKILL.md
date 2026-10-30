---
name: bootstrap-migration
description: Migrate a CommCare HQ app from Bootstrap 3 to Bootstrap 5.
argument-hint: <app_name> [--no-split]
---

# Bootstrap 3 → 5 Migration

Guide an AI agent through the Bootstrap migration process for a CommCare HQ app.

## Input

`$ARGUMENTS` — The Django app name (e.g., `reminders`, `accounting`) and optionally `--no-split` for small apps.

## Key Documentation

Read these before starting work on any migration:

- **Full migration guide (HTML):** `corehq/apps/styleguide/templates/styleguide/bootstrap5/migration_guide.html`
- **Per-change reference docs:** `corehq/apps/hqwebapp/utils/bootstrap/changes_guide/*.md` — each `todo B5: <change-type>` comment in migrated code references one of these files. Read the relevant guide before resolving a TODO.
- **Diff config:** `corehq/apps/hqwebapp/tests/data/bootstrap5_diff_config.json`

## Management Commands

All commands live in `corehq/apps/hqwebapp/management/commands/`:

| Command | Purpose |
|---|---|
| `migrate_app_to_bootstrap5 <app>` | Main migration tool. Key flags: `--no-split`, `--skip-all`, `--verify-references`, `--filename <file>` |
| `build_bootstrap5_diffs` | Rebuild diffs between split files. Use `--update_app <app>` first to update config. |
| `complete_bootstrap5_migration <app>` | Mark app complete, or un-split individual files with `--template <file>` / `--javascript <file>` |
| `complete_bootstrap5_report <ReportClassName>` | Mark a report view and its filters as migrated |

## Workflow

### 1. Determine app size and strategy

- **Small app** (fewer than ~10 views, no cross-app dependents): use `--no-split`
- **Large app** or **dependency of other apps**: use the split-files workflow

### 2. Pre-work: lint JavaScript

```
npx eslint corehq/apps/<app>
```

Commit lint fixes in a **separate PR** before any migration work.

### 3a. Small app ("no-split") migration

1. Run `./manage.py migrate_app_to_bootstrap5 <app> --no-split`
2. Resolve all `todo B5` comments — read the referenced `changes_guide/*.md` file for each
3. Apply `@use_bootstrap5` decorator to each view (or `use_bootstrap5 = True` for reports)
4. Test locally, verify no JS errors or visual regressions
5. Run `./manage.py complete_bootstrap5_migration <app>`

### 3b. Large app (split-files) migration

1. **Split files:** `./manage.py migrate_app_to_bootstrap5 <app> --skip-all`
   - May need multiple runs for nested template dependencies
2. **Update diff config:** `./manage.py build_bootstrap5_diffs --update_app <app>`, then `./manage.py build_bootstrap5_diffs`
3. **Verify references** (after rebasing master): `./manage.py migrate_app_to_bootstrap5 <app> --verify-references`
4. PR the split-files changes (automated changes only)
5. **Migrate views one-by-one** in subsequent PRs:
   - Add `@use_bootstrap5` decorator (or `use_bootstrap5 = True` for reports)
   - Switch template path from `bootstrap3/` to `bootstrap5/`
   - Resolve `todo B5` comments
   - Un-split files when their `bootstrap3` version is no longer referenced:
     `./manage.py complete_bootstrap5_migration <app> --template <file>`
6. **Complete:** `./manage.py complete_bootstrap5_migration <app>`

### 4. Resolving `todo B5` comments

Each TODO follows the pattern `todo B5: <change-type>`. The `<change-type>` maps to a file in `corehq/apps/hqwebapp/utils/bootstrap/changes_guide/`. **Always read the relevant guide file before making changes.** Common changes:

- **CSS class renames** (automated): `panel` → `card`, `well` → `card`, `glyphicon` → FontAwesome
- **HTML structure changes** (manual): dropdowns, navs, modals, forms, pagination
- **JS API changes** (manual): modal, tooltip, popover, tab, button APIs
- **Crispy forms** (manual): see `changes_guide/crispy.md`

### 5. Report views

Reports don't use `@use_bootstrap5`. Instead:
1. Set `use_bootstrap5 = True` on the report class
2. Temporarily set `debug_bootstrap5 = True` to find what needs migrating (don't commit this)
3. Migrate filters, templates, and JS as flagged
4. Run `./manage.py complete_bootstrap5_report <ReportClassName>`

### 6. Stylesheets (if the app has custom LESS files)

Convert LESS → SCSS manually. See the migration guide HTML for syntax examples (variables, mixins, media breakpoints, imports). Update `<link>` type from `text/less` to `text/scss`.

## Important Rules

- **Never mix lint fixes and migration changes in the same commit**
- **Never mix automated split-files changes and manual TODO fixes in the same PR**
- **Always rebuild diffs** (`build_bootstrap5_diffs`) before opening PRs — but don't include diff commits in staging branches
- **Re-migrate files** if `bootstrap3` versions diverge after merging master: `./manage.py migrate_app_to_bootstrap5 <app> --filename <file>`
- The goal is **functional parity**, not pixel-perfect matching — Bootstrap 5 uses different components (e.g., cards instead of panels)