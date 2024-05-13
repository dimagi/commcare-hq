`form-group` has been dropped. Use grid utilities instead.

Since we are opting for vertical forms (where the label is directly above the field),
the replacement for `form-group` is most likely just `mb-3` and the child `div` with a column
class surrounding the `form-control` element can be removed, along with the column class that
appears with the `<label>` `class` attribute. Most often, the `<label>` `class` only needs to
contain the `form-label` class now.
