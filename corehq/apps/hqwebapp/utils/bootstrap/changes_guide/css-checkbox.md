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
