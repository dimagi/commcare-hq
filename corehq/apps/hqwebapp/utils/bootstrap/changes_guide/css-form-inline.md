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
