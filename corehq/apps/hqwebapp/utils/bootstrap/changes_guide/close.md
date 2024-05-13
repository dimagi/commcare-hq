`close` has been renamed to `btn-close` (which we've automatically handled)

However, `&times;` in the HTML is no longer needed, as an embedded SVG is now used instead.
You can remove this.

An EXAMPLE for how to apply this change is provided below.

Previously:
```
<button type="button" class="close" data-dismiss="modal"><span aria-hidden="true">&times;</span></button>
```

Now:
```
<button type="button" class="btn-close" aria-label="Close"></button>
```
