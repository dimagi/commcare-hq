Form validation markup has been reworked, which includes dropping `has-success`.
In general, replace `has-success` and `help-block` with `is-valid` and `valid-feedback`.

An EXAMPLE for how to apply this change is provided below.
Please see docs for further details.

Previously:
```
    <div class="form-group has-success">
      <label for="id_happy_input" class="col-sm-4 control-label">
        Happy Input
      </label>
      <div class="col-sm-8 controls">
        <input type="text" name="happy_input" class="form-control" id="id_happy_input" />
        <span class='help-block'>Look at what a good job you did.</span>
      </div>
    </div>
```

Now:
```
    <div class="row mb-3">
      <label for="id_happy_input" class="form-label">
        Happy Input
      </label>
      <input type="text" name="happy_input" class="form-control is-valid" id="id_happy_input" />
      <div class='valid-feedback'>Look at what a good job you did.</div>
    </div>
```

Old docs: https://www.commcarehq.org/styleguide/organisms/#organisms-forms
New docs: https://www.commcarehq.org/styleguide/b5/organisms/forms/#field-errors
Bootstrap docs on validation: https://getbootstrap.com/docs/5.0/forms/validation/
