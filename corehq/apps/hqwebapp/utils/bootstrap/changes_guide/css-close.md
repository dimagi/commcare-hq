`close` has been renamed to `btn-close` (which we've automatically handled)

However, `&times;` in the HTML is no longer needed, as an embedded SVG is now used instead.
You can remove this.

In modal headers, `close` now comes *after* the `modal-title` instead of before it.

An EXAMPLE for how to apply this change is provided below.

Previously:
```
<div class="modal-header">
    <button type="button" class="close" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
    <h4 class="modal-title">Modal title</h4>
</div>
```

Now:
```
<div class="modal-header">
    <h4 class="modal-title" id="exampleModalLabel">Modal title</h4>
    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
</div>
```
