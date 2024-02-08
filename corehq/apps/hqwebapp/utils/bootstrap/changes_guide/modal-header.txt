The `modal` component was rewritten and now the close button should come after
the `modal-title`. Also, there is a new accessibility attribute `aria-labelledby`
which you can add to label the modal with the title. See documentation for details...

An EXAMPLE for how to apply this change is provided below.
Please see docs for further details.

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

See: Styleguide (B5) > Molecules > Modals for full example
Official Docs: https://getbootstrap.com/docs/5.3/components/modal/
