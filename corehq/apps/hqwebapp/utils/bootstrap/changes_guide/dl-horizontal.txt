`dl-horizontal` has been dropped.
Instead, use `.row` on `<dl>` and use grid column classes (or mixins) on its `<dt>` and `<dd>` children.

An EXAMPLE for how to apply this change is provided below.
Please see docs for further details.

Previously:
```
<dl class="dl-horizontal">
    <dt>foo</dt>
    <dd>foo</dd>
</dl>
```

Now:
```
<dl class="row">
    <dt class="col-3">foo</dt>
    <dd class="col-9">foo</dd>
</dl>
```
