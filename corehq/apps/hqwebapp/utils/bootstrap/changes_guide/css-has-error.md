Form validation markup has been reworked: `has-error` is dropped, replaced by `is-invalid` on the **input itself** and `invalid-feedback` on a **sibling** of that input. This breaks the B3 cascade — `has-error` on a container used to color every descendant help-block red. In B5 you must mark each piece explicitly.

The right migration depends on what `has-error` was wrapping. Below are the patterns HQ uses.

## 1. Canonical: form-group + label + input

B3:
```
<div class="form-group has-error">
  <label class="control-label col-sm-4">Error Input</label>
  <div class="col-sm-8 controls">
    <input class="form-control" id="id_error_input" />
    <span class="help-block">This is an error message.</span>
  </div>
</div>
```

B5:
```
<div class="row mb-3">
  <label class="field-label">Error Input</label>
  <div class="field-control">
    <input class="form-control is-invalid" id="id_error_input" />
    <div class="invalid-feedback">This is an error message.</div>
  </div>
</div>
```

Notes:
* `invalid-feedback` is hidden by default; it becomes visible via `.is-invalid ~ .invalid-feedback { display: block }`. So `invalid-feedback` **must be a later sibling** of the `is-invalid` input within the same parent.
* If the invalid state is toggled by Knockout, bind `css: {'is-invalid': hasError}` on the input. The CSS sibling selector handles the feedback's visibility — no separate `visible:` binding needed on `invalid-feedback`.

## 2. Standalone container (no input)

Pattern: a `has-error` div used purely to render a red error message — there is no input to mark as invalid. Common at the top of a form for save-time errors.

B3:
```
<div class="has-error float-end">
  <span class="help-block error-text d-none" id="form-errors">...</span>
</div>
```

B5: drop `has-error`, replace `help-block` with `text-danger` directly on the message.
```
<div class="float-end">
  <span class="text-danger error-text d-none" id="form-errors">...</span>
</div>
```

Do **not** introduce `invalid-feedback` here — without a sibling `.is-invalid` input, it won't display.

## 3. `has-warning`

B5 has no direct equivalent. There's `is-invalid` and `is-valid`, no warning variant. For warning messages, use a plain `text-warning` element.

B3:
```
<div class="has-warning">
  <span class="help-block">...</span>
</div>
```

B5:
```
<div class="text-warning small mt-1">...</div>
```

(The `small mt-1` matches the help-block's visual weight under an input.)

## 4. Table rows

A `<tr>` with `has-error` in B3 worked only via the cascade — coloring inner help-blocks red. B5 has no row-level invalid state, and `is-invalid` doesn't make sense on a `<tr>`.

Migration: drop the `has-error` binding from the `<tr>`, and color each inner message explicitly (`text-danger` for error, `text-warning` for warning).

B3:
```
<tr data-bind="css: {'has-error': validate}">
  <td>
    <div class="full-width-select2">...</div>
    <p class="help-block" data-bind="html: validate, visible: validate"></p>
  </td>
</tr>
```

B5:
```
<tr>
  <td>
    <div class="full-width-select2">...</div>
    <p class="text-danger small mb-0" data-bind="html: validate, visible: validate"></p>
  </td>
</tr>
```

If you want row-level highlight on a state, use B5's table state classes (`table-danger`, `table-warning`) — see next section.

## 5. Bootstrap table-state classes (`tr.warning`, `tr.danger`)

B3 had bare contextual classes on `<tr>` for row highlight: `warning`, `danger`, `success`, etc. B5 renames these to `table-warning`, `table-danger`, `table-success`. Update Knockout `css:` bindings accordingly.

B3:
```
<tr data-bind="css: {warning: isEmpty(), danger: isInvalid()}">
```

B5:
```
<tr data-bind="css: {'table-warning': isEmpty(), 'table-danger': isInvalid()}">
```

These are unrelated to form validation — they only highlight the row background.

## 6. Select2-wrapped controls — do not use `invalid-feedback`

A `<select>` with `staticSelect2: {}` (or any select2 KO binding) is hidden by select2 and replaced visually by a `<span class="select2-container">` sibling. Two consequences:

1. Adding `is-invalid` to the underlying `<select>` does **not** mark the select2 widget as invalid (no red border on the visible control).
2. The CSS sibling rule `.is-invalid ~ .invalid-feedback { display: block }` is unreliable here. Use `text-danger` + a `visible:` KO binding instead.

Pattern for KO-controlled select2 validation:
```
<select class="form-select" data-bind="staticSelect2: {}, value: workflow, ..."></select>
<div class="text-danger small mt-1" data-bind="visible: hasError">
  {% trans "Error message..." %}
</div>
```

The same applies to any KO-controlled error where the validation observable can toggle quickly — `text-danger` + `visible:` is the predictable pattern.

## Picking between `invalid-feedback` and `text-danger`

| Context | Use |
| --- | --- |
| Server-rendered form with `is-invalid` already on the input (Django form rendering, crispy forms) | `invalid-feedback` |
| Knockout-controlled validation on a plain `<input>` / `<textarea>` (no widget wrapping) | Either works; `invalid-feedback` is fine since the sibling chain is intact |
| Knockout-controlled validation on a select2-wrapped `<select>` | `text-danger` + `visible:` (sibling chain is brittle through select2) |
| Error message not tied to a specific input (top-of-form, table cells, save errors) | `text-danger` (`small mt-2 mb-0` for sizing) |
| Warning message | `text-warning` (no B5 equivalent for `has-warning`) |

**Spacing**: when replacing a B3 `<p class="help-block">` with `<p class="text-danger small ...">`, add `mt-2 mb-0`. 
  - `<p>` defaults to margin-top: 0 → without `mt-2`, the message touches the input with no breathing room.
  - `<p>` defaults to margin-bottom: 1rem (~16px) → without `mb-0`, there's wasted space below the message.

The rule of thumb: `invalid-feedback` requires a *reliable* sibling chain with `.is-invalid`. The chain breaks when widgets like select2 hide the original input. For anything KO-controlled with widget wrapping, `text-danger` + `visible:` is safer.
