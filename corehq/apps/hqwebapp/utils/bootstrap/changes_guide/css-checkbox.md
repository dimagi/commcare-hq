`checkbox` has been removed and rewritten.

An EXAMPLE for how to apply this change is provided below.
Please see docs for further details.

Previously:
```
<label class="checkbox" for="create_new_cases">
  <input type="checkbox"
         id="create_new_cases" />
  {% trans "Create new records" %}
</label>
```

Now:
```
<div class="form-check">
  <input class="form-check-input" type="checkbox" id="create_new_cases">
  <label class="form-check-label" for="create_new_cases">
    {% trans "Create new records" %}
  </label>
</div>
```

See: https://getbootstrap.com/docs/5.0/forms/checks-radios/#checks

## Horizontal-form gotcha: add `pt-0` to the row label

When a checkbox sits in the control column of a horizontal form (label on left, control on right, e.g. `.row mb-3` with `field-label` + `field-control`), `.form-check-input`'s `margin-top: 0.25em` (~4px) doesn't match `.col-form-label`'s `padding-top: calc(0.375rem + 1px)` (~7px). The checkbox sits ~3px above the label's text baseline.

Add `pt-0` to the `<label class="col-form-label field-label">` to remove the label's top padding, aligning the label with the checkbox top. This is the B5-documented fix — see the [B5 horizontal form docs](https://getbootstrap.com/docs/5.0/forms/layout/#horizontal-form) example using `<legend class="col-form-label col-sm-2 pt-0">` for the same reason.

```html
<!-- Wrong (post-migration, checkbox sits above label baseline) -->
<div class="row mb-3">
  <label class="col-form-label field-label">My Setting</label>
  <div class="field-control">
    <input class="form-check-input" type="checkbox" ...>
  </div>
</div>

<!-- Right -->
<div class="row mb-3">
  <label class="col-form-label field-label pt-0">My Setting</label>
  <div class="field-control">
    <input class="form-check-input" type="checkbox" ...>
  </div>
</div>
```

Only apply `pt-0` where the control column begins with a checkbox. For rows where the control is a text input or select, the default `col-form-label` padding is needed to vertically center the label against the input.
