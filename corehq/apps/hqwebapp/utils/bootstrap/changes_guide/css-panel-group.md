`panel-group` has been dropped in B5. The auto-rename script previously
mapped it to `card-group`, but those classes have **opposite** semantics:

- B3 `.panel-group` stacks panels **vertically** with no gaps (used for
  accordions and vertical groupings).
- B5 `.card-group` arranges cards **horizontally** in equal-width columns.

Replace `panel-group` with `d-flex flex-column gap-2` to recreate the
vertical-stack layout. B3's `panel-group` rendered panels nearly
edge-to-edge; `gap-2` (8px) is the closest natural utility — `gap-3`
(16px) reads visibly looser than the B3 original:

```
<!-- B3 -->
<div class="panel-group">
  <div class="panel">...</div>
  <div class="panel">...</div>
</div>
```

```
<!-- B5 -->
<div class="d-flex flex-column gap-2">
  <div class="card">...</div>
  <div class="card">...</div>
</div>
```

If you need adjacent cards joined edge-to-edge with no gap at all,
drop the `gap-2` and use `d-flex flex-column` alone.

If you actually want B5's horizontal `card-group` behavior (equal-width
side-by-side cards), use `class="card-group"` directly — it's not a
panel-group equivalent.

## Watch out: doubled spacing from gap + child margins

`.panel-group` in B3 used a descendant rule (`.panel-group .panel { margin-bottom: 0 }`) that zeroed each panel's bottom margin. The replacement parent `d-flex flex-column gap-*` does **not** zero its children — it just adds gap *between* siblings.

If the children carry their own `mb-3` (typical after the panel → card migration, which adds `mb-3` for natural vertical rhythm), the gap and the margin stack additively. With `gap-2` + `mb-3` you get 8px + 16px = ~24px between cards instead of the expected 8px.

When migrating a `panel-group`:

1. Pick a layout: `d-flex flex-column gap-*` (with gap) or `d-flex flex-column` (no gap).
2. **Audit every direct child** and drop `mb-3` (or whatever `mb-*`) — the parent's `gap-*` now owns the spacing. If you want tight stacking, drop both.
