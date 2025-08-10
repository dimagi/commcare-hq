`panel` has been dropped in favor of a new component `card`

We attempted a basic find-replace of css classes that have equivalents,
including classes we had to re-create.

However, there has been some restructuring to the `card` element itself that
might not be entirely translatable this way. Please review and adjust
accordingly.

Customized panel styles (`_panels.less`) has been migrated to card styles (`_card.scss`),
but not all of them are carefully reviewed. If you noticed some weird styling, please adjust
`_card.scss` accordingly.

```
<div class="panel-heading ">
    <h3 class="panel-title">
        {% trans ... %}
    </h3>
</div>
```
can be changed to
```
<div class="card-header">
    <h5 class="card-title mb-0">
        {% trans ... %}
    </h5>
</div>
```

See: https://getbootstrap.com/docs/5.3/components/card/
