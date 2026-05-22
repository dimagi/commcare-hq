## `card-title` (and the inner heading wrapper) → use a heading element with `card-header` class

When a B3 template wraps the title text inside a card-header with a heading element (`<h3 class="card-title">`, `<h4 class="card-title">`, etc.), drop the inner `card-title` wrapper and use a real heading element with `card-header` directly. This matches the [B5 docs example](https://getbootstrap.com/docs/5.3/components/card/#header-and-footer) and preserves semantic heading structure for accessibility. Downsize the heading level one step from the B3 original (B3's `.panel-title` rendered smaller than the plain HTML tag):

| Original tag | B5 heading-element class on card-header |
|---|---|
| `<h3 class="card-title">` | `<h4 class="card-header">` |
| `<h4 class="card-title">` | `<h5 class="card-header">` |
| `<h5 class="card-title">` | `<h6 class="card-header">` |

### Example — simple title

```
<!-- Before -->
<div class="card-header">
  <h4 class="card-title">{% trans "Advanced" %}</h4>
</div>

<!-- After -->
<h5 class="card-header">{% trans "Advanced" %}</h5>
```

### Example — title with non-heading siblings (buttons, search-box, etc.)

Use this when the card-header has more than just title text — e.g. action buttons, a search box, a status badge. Putting non-heading content inside an `<h*>` element is invalid HTML, so the card-header stays a `<div>` and a heading element wraps the title column inside:

```
<!-- Before -->
<div class="card-header">
  <h4 class="card-title">{% trans "Save Questions to Case Properties" %}</h4>
  <search-box ...></search-box>
</div>

<!-- After (grid pattern: see panel-case-actions-actions.md) -->
<div class="card-header row align-items-center g-0">
  <h5 class="col mb-0" data-bind="html: header"></h5>
  <div class="col-auto"><search-box ...></search-box></div>
</div>
```

The heading element is the title column inside the grid — semantic heading + matching font-size from the element itself (no `h5` utility class on the parent needed). The `mb-0` cancels the `<h5>` element's default margin-bottom so it aligns properly inside the grid row.

### Why

- A real heading element (`<h5>`) preserves semantic heading hierarchy. Screen readers, search engines, and accessibility tools rely on `<h*>` for navigation; `<div class="card-header h5">` looks like a heading but isn't one semantically.
- B5's `.card-title` is intended for titles inside the card body, not the bordered header — using it in the header conflicts with `.card-title`'s `margin-bottom: 0.5rem`.
- Downsize one level because B3's `.panel-title` set `font-size: ceil($font-size-base * 1.125)`, so a B3 `<h3 class="panel-title">` rendered smaller than a plain `<h3>`. One level down in B5 keeps the visual weight close to B3.

**Heading element margin**: Bootstrap applies `margin-bottom: 0.5rem` to all heading elements (`<h1>`–`<h6>`) by default. When the heading element IS the card-header (`<h5 class="card-header">`), `.card-header`'s own `margin-bottom: 0` rule overrides it — no action needed. But when the heading is the title column inside a grid card-header (`<h5 class="col">`), add `mb-0` to cancel the heading's default margin or it'll push the row off-center.

### KO bindings on the dropped heading move to the heading element

If the dropped `<h4 class="card-title">` had a Knockout binding (e.g. `data-bind="html: header"`), it moves to the new heading element:

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

If the card-header is laid out as a grid row with sibling buttons (see [`panel-case-actions-actions.md`](panel-case-actions-actions.md)), put `data-bind="html: header"` on the title `<h5 class="col">` rather than the card-header itself — otherwise the html binding would replace the buttons too.

### Related

- `card-title-nolink`: drops away as a side effect of the wrapper drop. B5's default card-header border-bottom serves the same visual-separation role the old `.card-title-nolink` rule provided.
- [`card-modern-gray-flex-header.md`](card-modern-gray-flex-header.md): the `.card-modern-gray > .card-header` SCSS rule makes the header a flex container with `min-height: 3rem`. Multi-child content collapses whitespace; see the doc for the `<span>` / `gap-*` workarounds.
