`close` has been renamed to `btn-close` (which we've automatically handled).

Manual changes:

* Remove the inner content (`&times;`, `×`, and any wrapping `<span>`).
  B5's `btn-close` uses an embedded SVG; inner text would render on top of it.
* Reorder the button to come AFTER `modal-title` in the modal header.
* Ensure the button has `aria-label="Close"`. Remove any `aria-hidden="true"`
  on the button itself — it hides the control from screen readers.
* Convert `<a class="btn-close">` to `<button type="button" class="btn-close">`.

## Example

Previously (canonical B3):
```
<div class="modal-header">
    <button type="button" class="close" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
    <h4 class="modal-title">Modal title</h4>
</div>
```

Now (B5):
```
<div class="modal-header">
    <h4 class="modal-title">Modal title</h4>
    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
</div>
```

## Pitfall: false positives in `{% trans %}` strings

The auto-rename replaces `close` with `btn-close` everywhere it matches,
including inside `{% trans %}` / `{% blocktrans %}` bodies where "close"
is the English verb. Find them with:

    grep -rn "btn-close" corehq/apps/<app>/templates | grep -v 'class="btn-close"'

Revert these in their own commit, separate from the structural changes.
