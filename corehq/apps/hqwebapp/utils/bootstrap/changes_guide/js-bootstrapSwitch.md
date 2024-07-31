The `bootstrap-switch` plugin is incompatible with Bootstrap 5, which has its own built-in switch widget.

A similar switch widget is built into Bootstrap 5 and does not require JavaScript instantiation.

An EXAMPLE for how to apply this change is provided below.
Please see docs for further details.

previously
```
$("#mySwitch").bootstrapSwitch();
```

now
```
<div class="form-check form-switch">
  <input class="form-check-input" type="checkbox" role="switch" id="mySwitch">
  <label class="form-check-label" for="mySwitch">Default switch checkbox input</label>
</div>
```

Old docs: https://bttstrp.github.io/bootstrap-switch/
New docs: https://getbootstrap.com/docs/5.1/forms/checks-radios/#switches
