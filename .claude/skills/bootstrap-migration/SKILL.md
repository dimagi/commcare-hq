---
name: bootstrap-migration
description: Migrate a CommCare HQ app from Bootstrap 3 to Bootstrap 5.
argument-hint: <app_name>
---

# Bootstrap 3 → 5 Migration

Guide an AI agent through the Bootstrap migration process for a CommCare HQ app or single view.

## On invocation

This skill is interactive. When invoked, do this **before reading the rest of the skill**:

1. **Ask the user which app they want to migrate.** Use `AskUserQuestion` with a free-text answer. Don't guess from `$ARGUMENTS` if it's empty.

2. **Detect whether the app is already split.** Check if `corehq/apps/<app>/templates/<app>/bootstrap3/` exists:
   ```
   ls corehq/apps/<app>/templates/<app>/bootstrap3 2>/dev/null
   ```
   If the directory exists (and contains files), the app is already split. Also cross-check against the status registry: `corehq/apps/hqwebapp/utils/bootstrap/status/bootstrap3_to_5.json`.

3. **Branch by state:**

   **(a) Not split yet → run Phase A (Split the app).** Tell the user the app will be split now and a PR will be opened with only the automated changes. Then follow the steps in **Phase A** below.

   **(b) Already split → ask which view to migrate.** Use `AskUserQuestion` to ask which template the user wants to work on. List the still-split templates from `corehq/apps/<app>/templates/<app>/bootstrap5/` (and any inside `partials/.../bootstrap5/`) as options. Then follow **Phase B** (Single-view migration).

Do not begin migration work until the user has answered both questions.

## Input

`$ARGUMENTS` is the Django app name (e.g. `reminders`, `accounting`), optional. If provided, treat it as a default for the first interactive question and confirm. If empty, ask the user. The template / view to migrate is always picked interactively from the list of still-split files — never via `$ARGUMENTS`.

## Key Documentation

Read these before starting work on any migration:

- **Full migration guide (HTML):** `corehq/apps/styleguide/templates/styleguide/bootstrap5/migration_guide.html`
- **Per-change reference docs:** `corehq/apps/hqwebapp/utils/bootstrap/changes_guide/*.md` — each `{# todo B5: <change-type> #}` comment in migrated code references one of these files. Read the relevant guide before resolving a TODO.
- **Custom-class decisions:** `corehq/apps/hqwebapp/utils/bootstrap/changes_guide/custom-classes/README.md` — HQ-specific class migration choices.
- **Rename spec:** `corehq/apps/hqwebapp/utils/bootstrap/spec/bootstrap_3_to_5.json` — declares which CSS classes auto-rename (`direct_css_renames`) vs. get flagged for manual review (`flagged_css_changes`, `flagged_js_plugins`). Useful for understanding what category a TODO falls into.
- **Diff config:** `corehq/apps/hqwebapp/tests/data/bootstrap5_diff_config.json`

## Management Commands

All commands live in `corehq/apps/hqwebapp/management/commands/`:

| Command | Purpose |
|---|---|
| `migrate_app_to_bootstrap5 <app>` | Main migration tool. Key flags: `--skip-all` (split without prompting on TODOs), `--verify-references`, `--filename <file>`. `--no-split` exists but is no longer recommended — see Workflow. |
| `build_bootstrap5_diffs` | Rebuild diffs between split files. Use `--update_app <app>` first to update config. |
| `complete_bootstrap5_migration <app>` | Mark app complete, or un-split individual files with `--template <file>` / `--javascript <file>` |
| `complete_bootstrap5_report <ReportClassName>` | Mark a report view and its filters as migrated |

## Workflow overview

Always use the **split-files workflow**, even for apps with only a handful of views. B5 migration is currently deprioritized — individual devs have limited time per push, and a single view can be substantially more complicated than its file count suggests (see form_view in app_manager). The `--no-split` path exists on the command but is no longer the recommended approach: it forces all view migrations into one PR, which becomes unreviewable and gets stranded if the dev runs out of time.

The migration of an app happens across many PRs:

1. **Lint pre-work** (separate PR) — `npx eslint corehq/apps/<app>`, fix what's flagged
2. **Phase A: Split the app** (one PR, automated only)
3. **Phase B: Migrate views one-by-one** (one PR per view)
4. **Mark the app complete** (after every view is migrated)

---

## Phase A — Split the app

Use when the app has no `bootstrap3/` and `bootstrap5/` template directories yet.

1. Confirm with the user that you're about to split. Tell them this PR will contain only automated changes — no manual TODO fixes.
2. Create a branch: `<initials>/b5/<app>_split` (use the user's git initials).
3. Run the split:
   ```
   ./manage.py migrate_app_to_bootstrap5 <app> --skip-all
   ```
   May need multiple runs for nested template dependencies — keep going until the command settles.
4. Update the diff registry:
   ```
   ./manage.py build_bootstrap5_diffs --update_app <app>
   ./manage.py build_bootstrap5_diffs
   ```
5. Verify references (only if you rebased master mid-split):
   ```
   ./manage.py migrate_app_to_bootstrap5 <app> --verify-references
   ```
6. Push the branch and **open a draft PR**. Use the project's PR template. Title: `Bootstrap 5 Migration — split <app>`. Body should note:
   - Automated split only, no manual changes
   - Followups will migrate each view in separate PRs
   - Label `DON'T REVIEW YET` if the user prefers (per their personal convention)
7. Do not start view migrations on this branch. Phase B happens on follow-up branches off master after this PR merges.

---

## Phase B — Migrate views one-by-one

Use when the app is already split (or after Phase A's PR has merged). One PR per view. See **Single-View Workflow** below for the full procedure.

After Phase B is complete for every view:

```
./manage.py complete_bootstrap5_migration <app>
```

Only succeeds when no split files remain across the entire app.

---

## Single-View Workflow (the one you'll do most)

A single view migration is its own PR. Branch name `<initials>/b5/<app>_<view>_view`. Order of work matters more than people expect.

### Phase 0 — Wire up the view first

In commit 1, flip the view's route to B5 (`@use_bootstrap5` decorator, or switch the template path from `bootstrap3/` to `bootstrap5/`). Reason: every subsequent commit can be verified by the user in their local browser. Wiring at the end means the user can't verify until the very end, and bisecting regressions becomes much harder. After commit 1, hand off to the user to confirm the B5 view loads at all before continuing.

### Phase 1 — Bootstrap (visible quick wins)

Resolve small, visually obvious todo types first: `css-glyphicon`, `css-close`, `inline-style` that are layout-sensitive, etc. Builds momentum and surfaces obvious regressions early when the user verifies.

### Phase 2 — Containers

`css-form-group`, `css-form-inline`, `css-panel-group`, `panel-appmanager`, `css-well`. These change the layout scaffolding. Doing them before inner pieces means inner-piece work lands on a stable layout — the user verifies layout once, then inner-piece verification doesn't need to re-check layout.

### Phase 3 — Inner pieces

`css-checkbox`, `css-select-form-control`, `css-has-error`, `css-has-warning`, `crispy`. These sit inside the layout and depend on it being stable.

### Phase 4 — Invisible cleanup

`inline-style` (when the utility class produces identical output), prettier/formatting drift. Save for last so each earlier reload gave the user a meaningful visual change to inspect. Format-only changes go in their own **`Refactor: ...`** commits, never bundled with logic.

### Commit by todo type, not by file

For each todo type, make one commit covering **every template** in the view's rendering path. The reviewer holds one rule (`css-form-group` migration pattern) and verifies N applications. Per-file commits force a reviewer context-switch on every commit.

After each per-type commit, **hand the user a verification checklist** for every site the commit touched (see *Browser verification* below). Don't proceed to the next todo type until the user confirms the current one looks right.

Order roughly matches the phases above. **Always bundle any `changes_guide/<type>.md` update into the same `Migrate <type>` commit** — the doc and the code that follows it should land together so a reviewer following the doc has the matching diff in front of them.

### Coupled todos

Some types can't be verified independently — do them back-to-back and batch the verification:

- **`css-form-inline` + `css-form-group`** — they share the inline-flex parent/child relationship. Migrating either alone produces an intermediate-broken state.
- **`css-select-form-control` + `css-form-inline`** — `w-auto` on a select only restores horizontal layout once the parent is a flex container.

---

## Critical: scope = rendering path, NOT directory

**A view's migration scope is every template `{% include %}`d transitively, not just files under `partials/<view-name>/bootstrap5/`.** The most common mistake (and source of "how did you miss it?" reviews) is grepping a single directory and declaring done.

**Audit procedure before declaring a view done:**

1. Start at the view's top-level template (e.g. `<app>/bootstrap5/<view>.html`)
2. `grep -rn "{% include "` against it and recurse into each included partial
3. Repeat until no new files
4. `grep "todo B5"` across ALL of them — including shared partials under `partials/bootstrap5/`, `hqmedia/partials/`, etc.

**`grep "todo B5"` alone is not proof of completeness.** The auto-migration only flags certain patterns (e.g. `<div class="form-group">`). Partials whose horizontal-form wrapper lives in the *includer* — not the partial itself — get split with **zero** todo markers but still carry un-migrated B3 patterns like `form-label col-md-2` + sibling `col-md-10`.

**Compensate with secondary greps:**
```
grep -rn 'form-label col-md-\|control-label\|class="col-md-[0-9]"' <view-files>
grep -rn 'has-warning\|has-success\|panel-group\|class="warning"\|class="danger"' <view-files>
grep -rn 'btn-default\|text-muted ' <view-files>
```

These catch orphaned horizontal-form fragments, contextual states, and other patterns the auto-flagger misses.

**Don't forget JS files that emit HTML.** The auto-flagger marks templates only, so JS that builds markup via string concatenation, template literals, or `.css(...)` calls slips through. When migrating a view, also grep the JS bundles feeding it:

```
grep -rn 'style="\|\.css(' corehq/apps/<app>/static/<app>/js/**/bootstrap5/
```

Example: `app_manager/.../bootstrap5/forms/advanced/actions.js` emits `<span style="font-weight: bold;">` into the case-action header via `data-bind="html: header"`. No `todo B5` marker, no template diff — but it's still a B3-era inline style. Replace with the equivalent `fw-*` / `d-*` / `text-*` utility class. Use a purpose-named class + scoped SCSS rule only when the styling is contextual (e.g. color against a dark background).

---

## Browser verification — produce a checklist, not a rendering

The agent **cannot** open a browser, render the page, or visually compare to staging/production. The user does that. The agent's job is to produce a thorough verification checklist so the user knows exactly what to look at after each migration commit.

After every meaningful migration commit, **ask the user to refresh the page and verify**, and supply the checklist for the affected region. A clean grep is **not** verification — never declare a todo type "done" without the user confirming visually.

### What the checklist must contain

**1. Feature flag / setup context.** Every feature flag, privilege, add-on, toggle, or feature_preview that gates UI on the view, with **how to enable each** so the user can reproduce the state. Walk the rendering path (templates + KO viewmodel + Python view) to surface these — `{% if request|toggle_enabled:'X' %}`, `{% if add_ons.X %}`, `domain_has_privilege(... privileges.X ...)`, etc.

Examples gathered from form_view migration (illustrative — every view has its own):

- `Display Conditions` add-on
- `FORM_LINK_WORKFLOW` privilege
- `DATA_DICTIONARY` privilege (+ a property marked deprecated)
- `USERCASE` feature
- `Visit Scheduler` privilege + Advanced Module + `module.has_schedule`
- `CUSTOM_INSTANCES` / `CUSTOM_ASSERTIONS` add-ons
- `session_endpoints_enabled`
- Multi-language app (for the "use for all languages" checkbox)
- Shadow form type
- `is_case_list_form` (set via "Registration Form Accessible from Case List" on a different module)

**2. Region-organized verification list.** Walk the page top-down and list each visually distinct region. For each region: what feature flag / setup is needed, what migration types touched it, and what the user should see vs. the B3 version. Organize by **page region**, not by todo type — the user sweeps each region once and checks all migrations that touch it together.

**Explicitly flag dropped B3 spacing shims.** Inline whitespace tricks like `&nbsp;`, `<br />`, `&times;`, and inline `padding`/`margin` styles often disappear during the migration because the new flex/grid primitives (`gap-*`, `mb-*`, etc.) own the spacing. The reviewer sees the deletion in the diff but can't tell whether the new layout actually handles it. In each affected region's verification entry, name the shim that was removed and ask the user to confirm spacing.

**3. Include this in the PR description.** Reviewers need the same context.

---


---

## Build the diff registry — separate commit, always

`./manage.py build_bootstrap5_diffs` rebuilds the expected B3↔B5 diff snapshots that the test gate compares against. **Run it before declaring a migration done** — forgetting is the most common reason CI is red after a clean grep.

The output goes in **its own commit**, never bundled with the template change that triggered it. Reviewers should be able to skip the diff-rebuild commit when reading the PR — they're mechanical regenerations, not logic changes.

When the command prompts to auto-commit, answer `y` and let it use its own commit message — no need to override.

---

## Editing change-guide docs

If you find a gap, ambiguity, or wrong example in `changes_guide/<type>.md` while migrating, bundle the fix into the same `Migrate <type>` commit so the reviewer sees the doc change and the code change together.
- Update `test_bootstrap_changes.py` if you change the first line of the doc — the unit test asserts the flagger message uses `startswith(...)` on the doc's opening sentence.

Keep doc edits succinct: state the rule and one example. Skip rationale and edge-case enumeration unless they're load-bearing for the reader. Don't append "caught in <template>:<line>" anecdotes — they age badly.

---

## Single-view completion (the un-split step)

After the view is verified and all view-scope todos are done, finalize each template:

```
./manage.py complete_bootstrap5_migration <app> --template <file>
```

For each file, this moves the B5 version out of `bootstrap5/` to the original path, deletes the B3 version, and updates references. **It refuses to un-split if any B3 reference still exists** outside the view's scope.

Pattern: form-view-only partials un-split cleanly; **shared partials stay split** (other un-migrated views still reference them). Don't force.

Then:
```
./manage.py build_bootstrap5_diffs --update_app <app>
./manage.py build_bootstrap5_diffs
```

Both auto-commit. Final tree shows the un-split files at their canonical location.

---

## Report views

Reports don't use `@use_bootstrap5`. Instead:

1. Set `use_bootstrap5 = True` on the report class
2. Temporarily set `debug_bootstrap5 = True` to find what needs migrating (don't commit this)
3. Migrate filters, templates, and JS as flagged
4. Run `./manage.py complete_bootstrap5_report <ReportClassName>`

---

## Stylesheets (custom LESS → SCSS)

Convert manually. See the migration guide HTML for syntax examples (variables, mixins, media breakpoints, imports). Update `<link>` type from `text/less` to `text/scss`. Don't port HQ-custom less rules wholesale — evaluate each for whether B5 defaults handle the case.

---

## Commit-message style

**Subjects are short and templated.** For the common cases:

- Migrate a todo type: `Migrate <type>` (e.g. `Migrate css-form-group`, `Migrate inline-style`). Bundle any related `changes_guide/<type>.md` updates into this commit.
- Format-only changes: `Refactor: <what>`
- Diff regen: let `build_bootstrap5_diffs` auto-commit with its own message; don't override.

**Put context in the body, not the subject.** Reviewers skim subjects and read bodies only when the diff isn't self-explanatory. Use the body for things the diff can't show: a tradeoff you made, a non-obvious reason, a known follow-up. Don't enumerate sites touched (the diff shows that) or paste multi-paragraph rationale (that belongs in the `changes_guide/<type>.md` doc).

Co-author trailer is fine to keep.

---

## Important rules

- **Never mix lint fixes and migration changes in the same commit**
- **Never mix automated split-files changes and manual TODO fixes in the same PR**
- **Always rebuild diffs** (`build_bootstrap5_diffs`) before opening PRs — in a **separate** commit
- **Don't push to a branch with an open PR without permission** from the maintainer
- **Don't add `Refactor: prettier/ruff format ...` commits unless required** by a hook. Many of them net-negative the PR.
- **Re-migrate files** if `bootstrap3` versions diverge after merging master: `./manage.py migrate_app_to_bootstrap5 <app> --filename <file>` — but only when needed; check first that diffs are clean.
- The goal is **functional parity**, not pixel-perfect matching — Bootstrap 5 uses different components (e.g. cards instead of panels)
- **Trust nothing about the auto-rename output** until verified against the rendered page
- **Prefer Bootstrap's grid (`row` + `col-*` / `col-auto`) over `d-flex` utilities whenever it fits the layout.** The grid is the canonical Bootstrap layout system, more self-documenting, more flexible (mixing `col-6` with `col-auto` is natural). Reach for `d-flex flex-wrap align-items-center gap-*` only when the markup needs to be a flat list of inline-flowing siblings with no per-element sizing intent (rare).
- **Don't rewrite an existing change-guide doc to prescribe your own pattern.** If the original guide is sparse but points a direction, follow it and flesh out the doc with examples in that direction. Self-written guides become self-justifying — if you cite your own rewrite to defend a migration decision, you've broken the feedback loop. When in doubt, ask the maintainer before deviating from the original guide's direction.
