## `appmanager-page-actions` → flex row with title

HQ-custom B3 class used to anchor a small "page-actions" block (the App Summary / View Submissions / Edit Form button cluster, or similar) to the top-right of a page, with the page title flowing alongside on the left. Implemented as `float: right; margin-top: 20px;` plus a `margin-right` on the title block reserving space for the float.

### Migration

Drop the class on the template. Replace with a single flex row that holds both the title and the actions:

```html
<!-- B3 -->
<div class="appmanager-page-actions">
  …action buttons…
</div>
<div class="appmanager-edit-title">
  …title…
</div>

<!-- B5 -->
<div class="d-flex flex-wrap align-items-center gap-2 mt-3">
  <div class="appmanager-edit-title flex-grow-1 me-0">
    …title…
  </div>
  <div class="d-flex gap-2 flex-shrink-0">
    …action buttons…
  </div>
</div>
```

### Why not just `float-end`?

The class's existing SCSS rule (`_content.scss`) carries a `max-width: $app-page-actions-width` (265px) added during the LESS→SCSS migration. Three or more buttons exceed that width and wrap to multiple lines. Even removing the max-width and leaving the float, the title block doesn't reliably sit alongside the float — block-level elements after a float only flow next to it when their inline content fits in the remaining horizontal space, which is fragile when widths shift across viewports.

Flex layout makes the alignment explicit:

- `flex-wrap` on the parent — narrow viewports drop the buttons onto a new row instead of overlapping the title.
- `flex-grow-1` on the title — absorbs leftover space so the buttons sit at the right.
- `flex-shrink-0` on the buttons block — never compress.
- `gap-2` — consistent spacing between flex items.
- `me-0` on the title — overrides the legacy `margin-right: calc($app-page-actions-width + 2rem)` from `_content.scss` (the reserved-space-for-float trick is no longer needed in a flex layout).

### SCSS

No new rule. The legacy `.appmanager-page-actions` rule in `app_manager/scss/includes/_content.scss` is left in place for templates still in B3 mode and for any B5 template that hasn't migrated yet (`app_view.html`, `module_view_heading.html` as of 2026-05-10). Delete the rule once all consumers migrate.
