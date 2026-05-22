## `card-title` (and the inner heading wrapper) → use a heading element with `card-header` class

Drop the inner `card-title` wrapper and put the heading element on the card-header directly. Downsize one level from the B3 original:

| Original tag | B5 heading-element class on card-header |
|---|---|
| `<h3 class="card-title">` | `<h4 class="card-header">` |
| `<h4 class="card-title">` | `<h5 class="card-header">` |
| `<h5 class="card-title">` | `<h6 class="card-header">` |

### Simple title

```
<!-- Before -->
<div class="card-header">
  <h4 class="card-title">{% trans "Advanced" %}</h4>
</div>

<!-- After -->
<h5 class="card-header">{% trans "Advanced" %}</h5>
```

### Title with sibling content (buttons, search-box, etc.)

`<h*>` can't contain non-heading content, so the card-header stays a `<div>` and the heading wraps just the title column. See [`panel-case-actions-actions.md`](panel-case-actions-actions.md) for the grid pattern.

```
<!-- Before -->
<div class="card-header">
  <h4 class="card-title">{% trans "Save Questions to Case Properties" %}</h4>
  <search-box ...></search-box>
</div>

<!-- After -->
<div class="card-header row align-items-center g-0">
  <h5 class="col mb-0" data-bind="html: header"></h5>
  <div class="col-auto"><search-box ...></search-box></div>
</div>
```

`mb-0` cancels the `<h5>`'s default bottom margin inside the grid row.

### KO bindings

`data-bind="html: header"` (or similar) moves from the dropped wrapper onto the new heading element:

```
<!-- Before -->
<div class="card-header clickable" data-bs-toggle="collapse"
     data-bind="attr: {href: ...}">
  <h4 class="card-title" data-bind="html: header"></h4>
</div>

<!-- After -->
<h5 class="card-header clickable" data-bs-toggle="collapse"
    data-bind="attr: {href: ...}, html: header">
</h5>
```

When the card-header is a grid row with siblings, the binding goes on the title `<h5 class="col">`, not the card-header — otherwise it would replace the siblings too.

### Related

- `card-title-nolink`: drops away with the wrapper.
- [`card-modern-gray-flex-header.md`](card-modern-gray-flex-header.md): grid-layout patterns for headers with sibling content.
