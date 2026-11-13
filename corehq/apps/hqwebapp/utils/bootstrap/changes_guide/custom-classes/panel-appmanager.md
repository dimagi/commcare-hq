## `panel-appmanager` → `card-modern-gray`

Despite the name, this class is essentially a duplicate of `.panel-modern-gray` (in `_hq/panels.less`). The only differentiator was a `.pagination { margin: 0 }` rule that overrode B3's default pagination margin (B5 has no default pagination margin, so this rule is dead in B5 anyway).

The right migration is to consolidate to the existing `.card-modern-gray` rather than create a new `.card-appmanager` parallel class.

### Treatment

| B3 LESS rule (`app_manager/less/panel.less`) | Treatment |
|---|---|
| `border: none` | Provided by `.card-modern-gray` |
| `background-color: lighten(@cc-bg, 3)` | Provided by `.card-modern-gray` |
| Nested `.panel-heading { padding, hover, .hq-help styling }` | Provided by `.card-modern-gray .card-header { ... }` |
| Nested `.panel-title-nolink { padding, border-bottom }` | Provided by `.card-modern-gray .card-title-nolink { ... }` |
| Nested `.collapsing { overflow: hidden }` | Provided by `.card-modern-gray .collapsing { ... }` |
| `.pagination { margin: 0 }` | **Dead in B5** — B5's `.pagination` has no default margin to override |
| `B3 .panel { margin-bottom: 20px }` (default) | Use `mb-3` utility on the template |

### Template

```
<!-- B3 -->
<div class="panel panel-appmanager">
  ...
</div>
```

```
<!-- B5 -->
<div class="card card-modern-gray mb-3>
 ...
</div>
```

The `mb-3` utility recreates B3's default `.panel { margin-bottom: 20px }` so stacked cards don't sit edge-to-edge.

### SCSS

No new rule needed. `.card-modern-gray` already exists in
`_cards.scss` and provides everything required.

The old `.panel-appmanager` rule in `app_manager/scss/_panel.scss` is left in place during the migration window — module-view templates (case_summary, releases, modules) may still reference it. They should consolidate to `.card-modern-gray` when they migrate, at which point the legacy `.panel-appmanager` rule can be removed entirely.
