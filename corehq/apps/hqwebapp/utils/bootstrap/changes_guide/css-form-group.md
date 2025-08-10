`form-group` has been dropped. Use grid utilities instead.

Take the following actions:
* Remove the `div` wrapper from the `form-group`'s first child, which contains the field's label.
* Replace the column classes (`col-lg-2`, etc.) from the `form-group`'s first child, usually a `<label>`,
with the `field-label` class. If the first child is a control container such as form actions, do not add
`field-label`, and instead apply the next step to the first child.
* Replace the column classes (`col-lg-2`, etc.) of the `form-group`'s second child with `field-control`.
This `div` should contain the field control (the actual input, which will often use the `form-control` class).
* Replace `form-group` with `row mb-3`.
* Replace `form-label` with `col-form-label` (Recommended by B5 offical doc: https://getbootstrap.com/docs/5.0/forms/layout/#horizontal-form)
* `form-control-text` can be dropped, replace it with using `align-items-center` in the container's class
