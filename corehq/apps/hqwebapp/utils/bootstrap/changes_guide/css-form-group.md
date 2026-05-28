`form-group` has been dropped in B5. What to replace it with depends on the context the form-group was used in. HQ templates use it in two distinct patterns; each gets a different treatment.

## 1. Horizontal form (canonical Bootstrap use)

Pattern:
```
<div class="form-group">
  <label class="form-label col-md-2">Field</label>
  <div class="col-md-10">
    <input class="form-control" ...>
  </div>
</div>
```

Migration:
* Replace `form-group` with `row mb-3`.
* Replace the column classes and `form-label` on the label (first child) with just the HQ `field-label` utility class. `field-label` is defined as `@extend .col-form-label, .col-12, .col-sm-4, .col-md-3, .col-lg-2;` — it includes `.col-form-label`'s padding (needed for vertical baseline alignment with a sibling input) **and** the responsive label-column widths. Don't add `col-form-label` alongside `field-label`; it's redundant.
* Pick the right control-column class based on the B3 original (see table below) — `field-control` is **not** always correct.
* If the first child is a control container (no label, e.g. form actions), apply the control-column class to it directly — skip `field-label`.
* `form-control-text` can be dropped, replace it with `mt-2`.

### Choose the control-column class to match the B3 original

`field-control` widens the control to `col-lg-10` (~83% of row). B3 templates often used **narrower** control widths intentionally — applying `field-control` blindly widens those rows 2-3×. Check the original B3 template:

| B3 control width | B5 replacement |
| --- | --- |
| `col-sm-10` / `col-md-9` / `col-lg-10` (canonical full width) | `field-control` |
| `col-sm-8` | `field-control` (close enough; ~67% → ~83%) or `col-md-8` for exact match |
| `col-sm-6` (e.g. multi-input subgroups) | `col-md-6` |
| `col-sm-4` (most common — single select / input rows) | `col-md-4` |
| `col-sm-1` / `col-sm-2` wrapping a button or icon | `col-md-auto` (B3 let buttons overflow narrow columns visually; B5 wraps the text into the column) |

Result for canonical full-width:
```
<div class="row mb-3">
  <label class="field-label">Field</label>
  <div class="field-control">
    <input class="form-control" ...>
  </div>
</div>
```

Result for narrow control:
```
<div class="row mb-3">
  <label class="field-label">Field</label>
  <div class="col-md-4">
    <input class="form-control" ...>
  </div>
</div>
```

## 2. Inside a flex container (formerly `.form-inline`)

Pattern:
```
<!-- Before the form-inline parent was migrated -->
<div class="form-inline">
  <div class="form-group">
    <label>Case Tag</label>
    <input class="form-control" ...>
  </div>
  ...other cells...
</div>
```

The `form-group` here was a label+input **grouping cell**. In B3, `.form-inline` cascaded `display: inline-block` onto the `form-group`, so each cell flowed inline alongside others, with label+input inside each cell also flowing inline (via the `.form-inline .form-control { display: inline-block }` rule).

After the parent migrates to `<div class="d-flex flex-wrap align-items-center gap-2">`, both cascades are gone. Just dropping `form-group` from the inner wrapper leaves a bare `<div>` that's `display: block`, so label + input stack vertically inside the cell — the inline behavior is lost.

Migration:
* Drop the `form-group` class.
* **Make the wrapping div itself a flex container** by adding `class="d-flex align-items-center gap-1"`. This restores label+input flowing inline inside the cell.
* Add `w-auto` to the form-control / form-select inside the cell so it sizes to content instead of stretching to 100%.

Result:
```
<div class="d-flex flex-wrap align-items-center gap-2">
  <div class="d-flex align-items-center gap-1">
    <label>Case Tag</label>
    <input class="form-control w-auto" ...>
  </div>
  ...other cells...
</div>
```

Alternative: if there's no reason to keep the grouping, drop the wrapping div entirely and let label+input become direct flex children of the outer container.

## Coupling with `css-form-inline`

Form-group sites inside a `form-inline` parent are coupled to the [`css-form-inline`](css-form-inline.md) migration. Both should land in the same commit — migrating either alone produces an intermediate-broken state where label+input stack. See also `feedback_b5_coupled_todos` in the related memory notes.
