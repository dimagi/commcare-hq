## `.card-modern-gray > .card-header` is a flex container — watch for whitespace collapse

`.card-modern-gray > .card-header` carries `display: flex; align-items: center; min-height: 3rem` (see `card-title.md` for why). The flex layout is great for vertical centering, but it collapses inter-element whitespace between direct flex children. Block-flow-era markup that relied on inline whitespace between siblings often breaks visually.

### Two patterns and their fixes

| Header content | Symptom after migration | Fix |
|---|---|---|
| Icon + text, e.g. `<i>…</i> Title` | Icon and text touch with no space | Wrap both in a `<span>`. Now the card-header has one flex item; whitespace inside the span renders normally. |
| Multiple inline siblings, e.g. `<i>…</i><i>…</i> Title` | All children touch (icons-text all crammed together) | Same fix: wrap the whole content in a `<span>`. `gap-2` is wrong here — it would also push the paired icons apart. |

For **title + non-heading sibling content** (action buttons, search box, etc.), don't try to fit it inside a heading-element card-header — use the grid pattern with a `<div>` card-header and an inner heading column. See [`panel-case-actions-actions.md`](panel-case-actions-actions.md) for the worked example.

### Worked examples

**Icon + paired icon + text** (case-preload header):

```html
<!-- Wrong (post-migration, before fix) -->
<h5 class="card-header">
  <i class="fa fa-arrow-right"></i><i class="fa-regular fa-file"></i>
  {% trans "Load the following properties into the form questions" %}
</h5>

<!-- Right -->
<h5 class="card-header">
  <span>
    <i class="fa fa-arrow-right"></i><i class="fa-regular fa-file"></i>
    {% trans "Load the following properties into the form questions" %}
  </span>
</h5>
```

**Icon + text** (case_summary case-type header):

```html
<!-- Wrong -->
<h5 class="card-header">
  <i class="fcc fcc-fd-external-case"></i>
  <!-- ko text: name --><!-- /ko -->
</h5>

<!-- Right (use gap-2 since only two children, both safe to space) -->
<h5 class="card-header gap-2">
  <i class="fcc fcc-fd-external-case"></i>
  <!-- ko text: name --><!-- /ko -->
</h5>
```

Either `gap-2` or wrap-in-span works here; `gap-2` is shorter when there are only two children that both deserve spacing.

### Decision shortcut

- One logical group inside the header → wrap in `<span>`, no `gap-*` needed
- Two-plus elements that should all be spaced apart → `gap-*` on the card-header
- Mixed: some children tight, others spaced → wrap the tight ones in `<span>`, use `gap-*` between top-level flex items
- Title + non-heading content (buttons, search box, etc.) → grid pattern with `<div>` card-header, heading element on the title column (see [`panel-case-actions-actions.md`](panel-case-actions-actions.md))
