`form-group` has been dropped. Use grid utilities instead.

Since we are opting for vertical forms (where the label is directly above the field), take the following actions:
* Remove the `div` wrapper from the `form-group`'s first child, which contains the field's label.
* Remove the column classes (`col-lg-2`, etc.) from the `form-group`'s first child, usually a `<label>`,
which contains the field's label. Most often, this will leave the label with just the `form-label` class.
* Remove the column classes (`col-lg-2`, etc.) from the `form-group`'s second child, which contains the field
control (the actual input, which will often use the `form-control` class).  Frequently, this will leave the `<div>`
without any other classes. If so, and if it has no other attributes, it can be removed.
* Replace `form-group` with `mb-3`.
