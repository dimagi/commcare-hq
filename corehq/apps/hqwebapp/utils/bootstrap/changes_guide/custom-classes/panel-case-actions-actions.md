## `panel-case-actions-actions` → drop the wrapper; integrate buttons into the card-header's flex row

HQ-custom B3 class that wrapped a button group (move + delete) absolutely-positioned at the top-right of its `.panel-case-actions` parent. The B5 replacement is **not** a `position-absolute` wrapper —
that was tried, but it's fragile (anchoring depends on an ancestor having `position: relative`) and produces visual artifacts. Use flex layout in the card-header instead: the buttons become flex siblings
of a `flex-grow-1` title span.

### Treatment

| B3 LESS rule (`panel.less`) | Treatment |
|---|---|
| `position: absolute; right: 10px; top: 8px` | **Drop.** No replacement — buttons live inside the card-header. |
| `> .btn { transition: background-color 1s; border: none }` | **Drop.** Cosmetic, not load-bearing. |

No new SCSS rule. Spacing between buttons comes from `gap-*` on the
card-header flex container.

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
<div class="card-header h5 d-flex align-items-center">
  <span class="flex-grow-1 clickable" data-bs-toggle="collapse"
        data-bind="attr: {href: ...}, html: header"></span>
  <a class="case-action-move btn btn-purple">...</a>     <!-- now siblings of -->
  <button class="case-action-remove btn btn-purple">...</button>  <!-- the title span -->
</div>
```

Three things change in the markup:

1. **The wrapper `<div class="panel-case-actions-actions">` is dropped.** Its two button children become direct flex siblings of the title inside the card-header.
2. **The `<h4 class="panel-title">` wrapper is also dropped** per [`card-title.md`](card-title.md), with the heading-size utility class moved to the card-header (`h5`).
3. **The click target moves**: in B3, `data-toggle="collapse"` lived on the `panel-heading` (the whole header was clickable). In B5, it moves to an inner `<span class="flex-grow-1 clickable">` so that clicking the action buttons doesn't also toggle the collapse. KO `data-bind="html: header"` rides along on the span — if it stayed on the card-header, the `html` binding would replace the buttons too.

For static-text titles (no KO binding), use `ms-auto` on the first action button instead of a `flex-grow-1` span — the static title doesn't need a flex-grow wrapper to push siblings to the end.

### SCSS

No new rule. The old `.panel-case-actions .panel-case-actions-actions` rule in `_panel.scss` has been removed — no B5 template uses `panel-case-actions`, so the rule was unreachable. The B3 LESS equivalent in `app_manager/less/panel.less` is untouched; templates still in B3 mode (`bootstrap3/case_config*.html`) continue to get the original styling from there.
