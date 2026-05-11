`form-inline` has been dropped in B5 with no direct equivalent. Replace with flex utilities that recreate the horizontal-row-with-wrap layout:

```
<!-- B3 -->                       <!-- B5 -->
<div class="form-inline">         <div class="d-flex flex-wrap align-items-center gap-2">
  <label>...</label>                <label>...</label>
  <input class="form-control">      <input class="form-control w-auto">
</div>                            </div>
```

Companion changes inside the migrated container:

* Add `w-auto` to `form-control` and `form-select` siblings — without it, B5's `width: 100%` default stretches them and forces a vertical stack.
* Replace `<br />` with `<div class="w-100"></div>`. In B3 form-inline (inline-block layout), `<br />` pushed the next item to a new line. In B5 flex layout, `<br />` is ignored — flex items just keep flowing and wrap by container width. A full-width flex item (`w-100`) is the B5 idiom for forcing a wrap to the next row.
* Drop redundant `&nbsp;&nbsp;` separators between siblings — flex `gap-2` handles spacing now.

The same rules apply transitively: if a `card`, `well` (now also migrated), or any other parent had B3 inline-block content, after the parent migration its children may now stack vertically because `form-control` defaults to `display: block` in B5. Add `d-flex flex-wrap align-items-center gap-2` to the parent and `w-auto` to the form controls.

## Audit nested form-controls, not just direct children

`w-auto` only fixes form-controls that are **direct children** of the new flex container. If a form-control is nested inside an inner wrapper (typically a leftover `<div class="form-group">` that pairs a `<label>` with an `<input>`), `w-auto` isn't enough on its own — the wrapping div is the flex item, and inside the wrapping div the form-control still has `display: block` which pushes the input to a new line below the label.

After migrating the form-inline parent, grep for `class="form-control"` and `class="form-select"` **at every nesting level inside the migrated container**. For each one inside a wrapping div, either:

- **Drop the wrapping div** so the label + input become direct flex children of the outer container (use this when the grouping has no other purpose), OR
- **Make the wrapping div itself a flex container**: add `class="d-flex align-items-center gap-1"` so label + form-control flow inline inside the cell. Combine with `w-auto` on the form-control as usual.

```
<!-- After css-form-inline migration of the parent only — still wrong -->
<div class="d-flex flex-wrap align-items-center gap-2">
  <div>                              <!-- wrapping div (formerly .form-group) -->
    <label>Case Tag</label>
    <input class="form-control" />   <!-- still display: block; width: 100% -->
  </div>                             <!-- → label and input stack vertically -->
</div>

<!-- Right: drop the wrapper -->
<div class="d-flex flex-wrap align-items-center gap-2">
  <label>Case Tag</label>
  <input class="form-control w-auto" />
</div>

<!-- Right: make the wrapper flex too -->
<div class="d-flex flex-wrap align-items-center gap-2">
  <div class="d-flex align-items-center gap-1">
    <label>Case Tag</label>
    <input class="form-control w-auto" />
  </div>
</div>
```

## Don't add `form-label` in inline contexts

B5's `.form-label` only adds `margin-bottom: 0.5rem` — appropriate for **label-above-input** vertical layouts. In a `d-flex align-items-center` row, that bottom margin is included in the flex item's margin box and pushes the label's visible text upward off the row's vertical center, producing a noticeable misalignment.

Use the right label class for the right layout:

| Layout                                | Label class              |
| ------------------------------------- | ------------------------ |
| Vertical (label above input)          | `form-label`             |
| Horizontal grid (label in adjacent column) | `col-form-label`    |
| Flex inline (label beside input, same row) | none (bare `<label>`) |

A bare `<label>` with no class renders identically to `form-label` except for the margin, so it's the right choice for the inline case.

## When form-inline is on a wrapper, not the inline-layout container

Sometimes form-inline sits on an outer element (e.g. a `<form>` wrapping `card-header` + `card-body`) but the actual inline children are inside `card-body`. In that case:

* Remove `form-inline` from the wrapper (no replacement needed there).
* Add `d-flex flex-wrap align-items-center gap-2` to the inner container that holds the inline children.

```
<!-- B3 -->
<form class="form-inline">
  <div class="card-header">...</div>
  <div class="card-body">
    <select class="form-control">...</select>
    <button>Submit</button>
  </div>
</form>

<!-- B5 -->
<form>
  <div class="card-header">...</div>
  <div class="card-body d-flex flex-wrap align-items-center gap-2">
    <select class="form-select w-auto">...</select>
    <button>Submit</button>
  </div>
</form>
```

If the layout has nested groupings (e.g. `<span>` wrapping a subset of the inline children), use `d-inline-flex flex-wrap align-items-center gap-2` on the wrapping span so it acts as a flex container while remaining inline within the parent flex.
