`well` and `well-sm` have been dropped in B5 with no direct equivalent. The closest pattern is a card with a card-body for padding.

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

- The auto-rename script will replace `well` with `card`, but `card` alone has no padding — content butts up against the border. Add `card-body` (gives 1rem padding, the B5 default) to recreate the visual weight of B3's well.
- Use `p-2` (0.5rem padding) when the original was `well-sm` to keep the smaller padding ratio.
- **Always include `mb-3`** to reproduce B3's implicit `well { margin-bottom: 20px }` rule. B5's `.card` has no default margin, so without `mb-3` the well sits flush against whatever follows it (next card, sibling button, etc.). This is easy to miss because the visual gap was never in the HTML — it was in Bootstrap 3's stylesheet.
- Combining `card` and `card-body` on the same `<div>` keeps the markup flat — fine when the card is just a body. If you later add a `card-header` or `card-footer`, switch to the nested form so they can sit as siblings of the body:
  ```
  <div class="card">
    <div class="card-header">...</div>
    <div class="card-body">...</div>
  </div>
  ```
- If the original B3 well's *content* was a horizontal flow (e.g. `<strong>` + text + `<input class="form-control">` siblings rendered inline thanks to B3's inline-block defaults), lay out the B5 card's children using Bootstrap's grid. Add `row align-items-center g-2` to the card-body and wrap each child in `<div class="col-auto">`. See [`css-form-inline.md`](css-form-inline.md) for the full pattern. Drop any `&nbsp;&nbsp;` separators between siblings — the row's `g-2` gutter handles spacing.
