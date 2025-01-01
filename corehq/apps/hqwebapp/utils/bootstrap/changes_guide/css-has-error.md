Form validation markup has been reworked, which includes dropping `has-error`.
In general, replace `has-error` and `help-block` with `is-invalid` and `invalid-feedback`.
Note that `invalid-feedback` must be a **sibling** of an input with `is_invalid`, or it will be hidden.
This is a change from `has-error`, which was used on containers and would apply to all descendants.

An EXAMPLE for how to apply this change is provided below.
Please see docs for further details.

Previously:
```
    <div class="form-group has-error">
      <label for="id_error_input" class="col-sm-4 control-label">
        Error Input
      </label>
      <div class="col-sm-8 controls">
        <input type="text" name="error_input" class="form-control" id="id_error_input" />
        <span class='help-block'>This is an error message.</span>
      </div>
    </div>
```

Now:
```
    <div class="row mb-3">
      <label for="id_error_input" class="form-label field-label">
        Error Input
      </label>
      <div class="field-control">
        <input type="text" name="error_input" class="form-control is-invalid" id="id_error_input" />
        <div class='invalid-feedback'>This is an error message.</div>
      </div>
    </div>
```

Old docs: https://www.commcarehq.org/styleguide/organisms/#organisms-forms
New docs: https://www.commcarehq.org/styleguide/b5/organisms/forms/#field-errors
Bootstrap docs on validation: https://getbootstrap.com/docs/5.0/forms/validation/
