## `panel-case-actions-actions` → drop the wrapper; lay out the card-header as a grid row

HQ-custom B3 class that wrapped a button group (move + delete) absolutely-positioned at the top-right of its `.panel-case-actions` parent. The B5 replacement is **not** a `position-absolute` wrapper — that was tried, but it's fragile (anchoring depends on an ancestor having `position: relative`) and produces visual artifacts. Lay out the card-header as a Bootstrap grid row: the title fills, the action buttons sit in `col-auto` siblings on the right.

### Treatment

| B3 LESS rule (`panel.less`) | Treatment |
|---|---|
| `position: absolute; right: 10px; top: 8px` | **Drop.** No replacement — buttons live inside the card-header. |
| `> .btn { transition: background-color 1s; border: none }` | **Drop.** Cosmetic, not load-bearing. |

No new SCSS rule. `.row` provides flex layout; `.col-auto` widths push the buttons to the right edge.

### Template

```html
<!-- B3 -->
<div class="panel-heading clickable" data-toggle="collapse"
     data-bind="attr: {href: ...}">
  <h4 class="panel-title panel-title-nolink" data-bind="html: header"></h4>
</div>
<div class="panel-case-actions-actions">                    <!-- the wrapper -->
  <a class="case-action-move btn btn-purple">...</a>
  <button class="case-action-remove btn btn-purple">...</button>
</div>

<!-- B5 -->
<div class="card-header h5 row align-items-center g-0">
  <div class="col clickable" data-bs-toggle="collapse"
       data-bind="attr: {href: ...}, html: header"></div>
  <div class="col-auto">
    <a class="case-action-move btn btn-purple">...</a>
  </div>
  <div class="col-auto">
    <button class="case-action-remove btn btn-purple">...</button>
  </div>
</div>
```

Three things change in the markup:

1. **The wrapper `<div class="panel-case-actions-actions">` is dropped.** Its two button children become `col-auto` siblings of the title column inside the card-header.
2. **The `<h4 class="panel-title">` wrapper is also dropped** per [`card-title.md`](card-title.md), with the heading-size utility class moved to the card-header (`h5`).
3. **The click target moves**: in B3, `data-toggle="collapse"` lived on the `panel-heading` (the whole header was clickable). In B5, it moves to the title `<div class="col clickable">` so that clicking the action buttons doesn't also toggle the collapse. KO `data-bind="html: header"` rides along on the title column — if it stayed on the card-header, the `html` binding would replace the buttons too.

`.col` (no number) takes `flex: 1 0 0%` — it eats all remaining horizontal space, pushing the `.col-auto` button columns to the right edge. No `ms-auto` or `flex-grow-1` needed. `g-0` zeros the row's default 1.5rem gutter, which would otherwise add unwanted padding inside the card-header.

### SCSS

No new rule. The old `.panel-case-actions .panel-case-actions-actions` rule in `_panel.scss` has been removed — no B5 template uses `panel-case-actions`, so the rule was unreachable. The B3 LESS equivalent in `app_manager/less/panel.less` is untouched; templates still in B3 mode (`bootstrap3/case_config*.html`) continue to get the original styling from there.
