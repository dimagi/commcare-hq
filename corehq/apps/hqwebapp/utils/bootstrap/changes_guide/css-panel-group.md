`panel-group` has been dropped in B5. The auto-rename script previously
mapped it to `card-group`, but those classes have **opposite** semantics:

- B3 `.panel-group` stacks panels **vertically** with no gaps (used for
  accordions and vertical groupings).
- B5 `.card-group` arranges cards **horizontally** in equal-width columns.

Replace `panel-group` with `d-flex flex-column gap-3` to recreate the
vertical-stack-with-spacing layout:

```
<!-- B3 -->                         <!-- B5 -->
<div class="panel-group">           <div class="d-flex flex-column gap-3">
  <div class="panel">...</div>        <div class="card">...</div>
  <div class="panel">...</div>        <div class="card">...</div>
</div>                              </div>
```

If you need adjacent cards joined edge-to-edge with no gap (the closest
visual match to B3's panel-group), drop the `gap-3` and use
`d-flex flex-column` alone.

If you actually want B5's horizontal `card-group` behavior (equal-width
side-by-side cards), use `class="card-group"` directly — it's not a
panel-group equivalent.
