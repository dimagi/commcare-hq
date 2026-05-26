`form-inline` has been dropped in B5 with no direct equivalent. **Prefer Bootstrap's grid** (`row` + `col-auto`) — that's what Bootstrap's [inline forms docs](https://getbootstrap.com/docs/5.3/forms/layout/#inline-forms) recommend:

```
<!-- B3 -->
<div class="form-inline">
  <label>...</label>
  <input class="form-control">
</div>
```

```
<!-- B5 -->
<div class="row align-items-center g-2">
  <div class="col-auto"><label class="col-form-label">...</label></div>
  <div class="col-auto"><input class="form-control"></div>
</div>
```

Notes:
* Each inline element (label, input, select, span, button) wraps in `<div class="col-auto">`.
* `g-2` provides 0.5rem horizontal AND vertical gutter (handles wrap spacing).
* `<label>` gets `col-form-label` — designed for "label in adjacent column" layouts, padding aligns the label baseline with the form-control content area.
* `<select>` migrates `form-control` → `form-select` per [`css-select-form-control.md`](css-select-form-control.md).
* For a forced line break (formerly `<br />`), use `<div class="col-12"></div>` — full-width column wraps subsequent items to the next row.

## When form-inline is on a wrapper, not the inline-layout container

Sometimes form-inline sits on an outer element (e.g. a `<form>` wrapping `card-header` + `card-body`) but the actual inline children are inside `card-body`. In that case:

* Remove `form-inline` from the wrapper (no replacement needed there).
* Add `row align-items-center g-2` to the inner container that holds the inline children, and wrap each child in `col-auto`.

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
  <div class="card-body row align-items-center g-2">
    <div class="col-auto"><select class="form-select">...</select></div>
    <div class="col-auto"><button>Submit</button></div>
  </div>
</form>
```

If the layout has nested groupings (e.g. an inner subset of inline children that should stay together), wrap them in a `<div class="col-auto">` containing its own `<div class="row align-items-center g-2">` with `col-auto` children inside.
