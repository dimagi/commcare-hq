`well` and `well-sm` have been dropped in B5 with no direct
equivalent. The closest pattern is a card with a card-body for
padding.

```
<!-- B3 -->
<div class="well-sm">
  ...content...
</div>

<div class="well">
  ...content...
</div>
```

```
<!-- B5 -->
<div class="card card-body p-2 mb-3">
  ...content...
</div>

<div class="card card-body mb-3">
 ...
</div>
```

Notes:

- The auto-rename script will replace `well` with `card`, but `card`
  alone has no padding — content butts up against the border. Add
  `card-body` (gives 1rem padding, the B5 default) to recreate the
  visual weight of B3's well.
- Use `p-2` (0.5rem padding) when the original was `well-sm` to keep
  the smaller padding ratio.
- **Always include `mb-3`** to reproduce B3's implicit
  `well { margin-bottom: 20px }` rule. B5's `.card` has no default
  margin, so without `mb-3` the well sits flush against whatever
  follows it (next card, sibling button, etc.). This is easy to miss
  because the visual gap was never in the HTML — it was in
  Bootstrap 3's stylesheet.
- Combining `card` and `card-body` on the same `<div>` keeps the
  markup flat (no extra wrapper). This works in B5 when you don't
  need card-header / card-footer alongside the body. Use the
  conventional nested form (`<div class="card"><div class="card-
  body">...</div></div>`) when you do.
- If the original B3 well's *content* was a horizontal flow (e.g.
  `<strong>` + text + `<input class="form-control">` siblings rendered
  inline thanks to B3's inline-block defaults), the B5 card needs
  `d-flex flex-wrap align-items-center gap-2` and the form-controls
  inside need `w-auto`. Otherwise B5's `display: block` form-controls
  will stack vertically. Drop any `&nbsp;&nbsp;` separators between
  siblings — flex `gap-2` handles spacing.
