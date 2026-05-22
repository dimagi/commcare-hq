## `.card-modern-gray > .card-header` is a flex container — watch for whitespace collapse

`.card-modern-gray > .card-header` carries `display: flex; align-items: center; min-height: 3rem` (see `card-title.md` for why). The flex layout is great for vertical centering, but it collapses inter-element whitespace between direct flex children — so B3 markup that relied on a space between siblings (e.g. `<i>…</i> Title`) often loses that space after migration.

For **title + non-heading sibling content** (action buttons, search box, etc.), don't try to fit it inside a heading-element card-header — use the grid pattern with a `<div>` card-header and an inner heading column. See [`panel-case-actions-actions.md`](panel-case-actions-actions.md).

### Fix: wrap inline content in a `<span>`

Paired icons + text (case-preload header):

```html
<h5 class="card-header">
  <span>
    <i class="fa fa-arrow-right"></i><i class="fa-regular fa-file"></i>
    {% trans "Load the following properties into the form questions" %}
  </span>
</h5>
```

**Rendered output:**

```
→📄 Load the following properties…  (icons touch each other, one space before text)
```

**Mechanism:** the `<span>` wrap puts the content back into inline flow, where HTML's normal whitespace rules apply (the newline-and-indent between `</i>` and `{% trans %}` renders as one space).
