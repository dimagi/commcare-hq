## `card-title` (and the inner heading wrapper) → drop the wrapper element

When a B3 template wraps the title text inside a card-header with a heading element (`<h3>`, `<h4>`, etc.), drop the heading and add a heading-size utility class to the card-header instead. Downsize the class one level from the original tag:

| Original tag | Heading-size class on card-header |
|---|---|
| `<h3 class="card-title">` | `h4` |
| `<h4 class="card-title">` | `h5` |
| `<h5 class="card-title">` | `h6` |

### Example

```
<!-- Before -->
<div class="card-header">
  <h4 class="card-title">{% trans "Advanced" %}</h4>
</div>

<!-- After -->
<div class="card-header h5">
  {% trans "Advanced" %}
</div>
```

### Why

- B5's `.card-title` ships with `margin-bottom: 0.5rem`, which leaves the title sitting asymmetrically inside the card-header (extra space below, none above) — not vertically centered. Letting the card-header own the typography directly removes the asymmetry.
- Downsize one level because B3's `.panel-title` set `font-size: ceil($font-size-base * 1.125)`, so a B3 `<h3 class="panel-title">` rendered smaller than a plain `<h3>`. One level down in B5 keeps the visual weight close to B3.

### KO bindings on the dropped heading move to the card-header

If the dropped heading element had a Knockout binding (e.g. `data-bind="html: header"`), merge it into the card-header's existing `data-bind`:

```
<!-- Before -->
<div class="card-header clickable" data-bs-toggle="collapse"
     data-bind="attr: {href: ...}">
  <h4 class="card-title" data-bind="html: header"></h4>
</div>

<!-- After -->
<div class="card-header clickable h5" data-bs-toggle="collapse"
     data-bind="attr: {href: ...}, html: header">
</div>
```

If the card-header is a flex container with sibling buttons (see [`panel-case-actions-actions.md`](panel-case-actions-actions.md)), put the `data-bind="html: header"` on the flex-grow-1 title span rather than the card-header itself — otherwise the html binding would replace the buttons too.

### Old `card-title-nolink` padding was load-bearing — now `min-height` on the card-header

B3 templates often paired `card-title` with `card-title-nolink` (`<h4 class="card-title card-title-nolink">`) when the title wasn't a clickable accordion-style header. Its old SCSS rule —

```scss
.panel-modern-gray .panel-title-nolink {
  padding: 15px 15px;
  border-bottom: 1px solid @cc-bg;
}
```

— looked decorative but was load-bearing: the `padding: 15px 15px` sized the card-header to a fixed-tall box. That mattered for templates that mount conditional content into the header (e.g. the search-box in `case-config:case-transaction:case-properties`) — without a tall header, the header animates from "title only" to "title + search-box" when the conditional content appears.

The wrapper drop above removes the rule. Its height-absorbing role is now carried by `.card-modern-gray > .card-header` —

```scss
.card-modern-gray > .card-header {
  display: flex;
  align-items: center;
  min-height: 3rem;
}
```

— where `min-height` locks the header height and flex centers the title regardless of how much extra space the min-height contributes. If you migrate another template with conditional header content and find the header still grows, increase the `min-height` rather than re-introducing the inner wrapper.

**Heads-up**: making card-header a flex container also collapses whitespace between its direct children. If your migrated header has an icon next to text (or any multi-element content), you may need `gap-*` or a `<span>` wrapper to preserve visual spacing. See [`card-modern-gray-flex-header.md`](card-modern-gray-flex-header.md).

### Related

- `card-title-nolink`: drops away as a side effect of the wrapper drop above. Was previously styled by `.card-modern-gray .card-title-nolink { padding, border-bottom }` (now removed) — B5's default card-header border-bottom serves the same visual-separation role.
- [`card-modern-gray-flex-header.md`](card-modern-gray-flex-header.md): whitespace-collapse gotchas in the flex-converted card-header.
