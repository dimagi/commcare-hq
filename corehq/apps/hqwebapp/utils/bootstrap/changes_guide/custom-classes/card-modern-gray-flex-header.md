## `.card-modern-gray > .card-header` is a flex container — watch for whitespace collapse

`.card-modern-gray > .card-header` carries `display: flex; align-items: center; min-height: 3rem` (see `card-title.md` for why). The flex layout is great for vertical centering, but it collapses inter-element whitespace between direct flex children. Block-flow-era markup that relied on inline whitespace between siblings often breaks visually.

### Three patterns and their fixes

| Header content | Symptom after migration | Fix |
|---|---|---|
| Icon + text, e.g. `<i>…</i> Title` | Icon and text touch with no space | Wrap both in a `<span>`. Now the card-header has one flex item; whitespace inside the span renders normally. |
| Multiple inline siblings, e.g. `<i>…</i><i>…</i> Title` | All children touch (icons-text all crammed together) | Same fix: wrap the whole content in a `<span>`. `gap-2` is wrong here — it would also push the paired icons apart. |
| Title + sibling element, e.g. title text + action buttons or search box | Children sit edge-to-edge with no visual gap | Use `gap-2` on the card-header. If the title must absorb leftover space (push siblings to the end), wrap the title in `<span class="flex-grow-1">`. |

### Worked examples

**Icon + paired icon + text** (case-preload header):

```html
<!-- Wrong (post-migration, before fix) -->
<div class="card-header h5">
  <i class="fa fa-arrow-right"></i><i class="fa-regular fa-file"></i>
  {% trans "Load the following properties into the form questions" %}
</div>

<!-- Right -->
<div class="card-header h5">
  <span>
    <i class="fa fa-arrow-right"></i><i class="fa-regular fa-file"></i>
    {% trans "Load the following properties into the form questions" %}
  </span>
</div>
```

**Icon + text** (case_summary case-type header):

```html
<!-- Wrong -->
<div class="card-header h5">
  <i class="fcc fcc-fd-external-case"></i>
  <!-- ko text: name --><!-- /ko -->
</div>

<!-- Right (use gap-2 since only two children, both safe to space) -->
<div class="card-header h5 gap-2">
  <i class="fcc fcc-fd-external-case"></i>
  <!-- ko text: name --><!-- /ko -->
</div>
```

Either `gap-2` or wrap-in-span works here; `gap-2` is shorter when there are only two children that both deserve spacing.

**Title + action buttons** (case-properties header):

```html
<div class="card-header h5 gap-2">
  <span class="flex-grow-1">
    <i class="fa fa-arrow-right"></i><i class="fa fa-save"></i>
    {% trans "Save Questions to Case Properties" %}
  </span>
  <div data-bind="if: searchAndFilter">
    <search-box ...></search-box>
  </div>
</div>
```

`gap-2` spaces the title span from the search-box; `flex-grow-1` on the title span makes it absorb leftover width so the search-box sits at the end.

### Decision shortcut

- One logical group inside the header → wrap in `<span>`, no `gap-*` needed
- Two-plus elements that should all be spaced apart → `gap-*` on the card-header
- Mixed: some children tight, others spaced → wrap the tight ones in `<span>`, use `gap-*` between top-level flex items
