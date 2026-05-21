## `appmanager-page-actions` → grid row with title

HQ-custom B3 class used to anchor a small "page-actions" block (the App Summary / View Submissions / Edit Form button cluster, or similar) to the top-right of a page, with the page title flowing alongside on the left. Implemented as `float: right; margin-top: 20px;` plus a `margin-right` on the title block reserving space for the float.

### Migration

Drop the class on the template. Replace with a Bootstrap grid row that holds both the title and the actions:

```html
<!-- B3 -->
<div class="appmanager-page-actions">
  …action buttons…
</div>
<div class="appmanager-edit-title">
  …title…
</div>

<!-- B5 -->
<div class="row align-items-center mt-3 g-2">
  <div class="appmanager-edit-title col">
    …title…
  </div>
  <div class="col-auto d-flex gap-2">
    …action buttons…
  </div>
</div>
```

### Why not just `float-end`?

The class's existing SCSS rule (`_content.scss`) carries a `max-width: $app-page-actions-width` (265px) added during the LESS→SCSS migration. Three or more buttons exceed that width and wrap to multiple lines. Even removing the max-width and leaving the float, the title block doesn't reliably sit alongside the float — block-level elements after a float only flow next to it when their inline content fits in the remaining horizontal space, which is fragile when widths shift across viewports.

The grid row makes the alignment explicit and reads naturally:

- `.col` on the title — fills available horizontal space, pushing the buttons to the right.
- `.col-auto` on the buttons block — sized to content, no shrink.
- `align-items-center` — vertically centers the title and buttons.
- `g-2` — 0.5rem gutter between the title and buttons.
- `.row` wraps to a new line on narrow viewports automatically (flex-wrap is on by default).
- Inner `d-flex gap-2` on the buttons block — flex grouping for the buttons themselves (correct use of flex for inline-flowing button cluster).

### SCSS

No new rule. The legacy `.appmanager-page-actions` rule in `app_manager/scss/includes/_content.scss` is left in place for templates still in B3 mode and for any B5 template that hasn't migrated yet (`app_view.html`, `module_view_heading.html` as of 2026-05-10). Delete the rule once all consumers migrate.
