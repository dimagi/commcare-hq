`panel` has been dropped in favor of a new component `card`

We attempted a basic find-replace of css classes that have equivalents,
including classes we had to re-create.

However, there has been some restructuring to the `card` element itself that
might not be entirely translatable this way. Please review and adjust
accordingly.

Customized panel styles (`_panels.less`) have been migrated to card styles (`_cards.scss`),
but not all of them have been reviewed. If you noticed some weird styling, please adjust
`_cards.scss` accordingly.

```
<div class="panel-heading ">
    <h3 class="panel-title">
        {% trans ... %}
    </h3>
</div>
```
can be changed to
```
<div class="card-header">{% trans ... %}</div>
```

See: https://getbootstrap.com/docs/5.3/components/card/

## HQ-custom panel classes

Many HQ templates pair `.panel` with HQ-custom classes
(`.panel-appmanager`, `.panel-case-actions`, etc.) that the
auto-rename does not handle. See
[`custom-classes/`](custom-classes/README.md) for the per-class
decisions and the principle ("minimize stylesheet, keep color")
that governs them.
