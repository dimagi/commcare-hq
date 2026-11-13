## `panel-case-actions` → `card-case-actions`

HQ-custom B3 class that gave case-action panels a dark-accent color scheme. The B3 version also set `position: relative` so an inner `.panel-case-actions-actions` wrapper could be absolutely-positioned
for the move/delete button overlay — but in B5 we drop that pattern entirely (see [`panel-case-actions-actions.md`](panel-case-actions-actions.md)) and integrate the buttons as flex children of the card-header. So this class is now **color only**.

### Treatment

| B3 LESS rule (`panel.less`) | Treatment |
|---|---|
| `position: relative` | **Drop.** No longer needed — buttons are flex children of card-header, not absolutely-positioned. |
| `background-color: lighten(@cc-dark-cool-accent-hi, 3)` | **Keep** in `.card-case-actions` SCSS. |
| `> .panel-heading { background-color: @cc-dark-cool-accent-mid; color: white; }` | **Keep**, but rewrite as `> .card-header { ... }`. |
| `> .panel-heading .text-muted { color: ... }` | **Keep**. Add `!important` to the override — B5's `.text-muted` utility ships with `!important`, so without it the muted "close" / "update" labels in the header are nearly invisible against the dark-purple bg. |
| Nested `.panel-appmanager { border-radius: 10px; .well { ... } }` | **Drop.** B5 uses different class names; the cosmetic radius wasn't load-bearing. |

### Template

```
<!-- B3 -->
<div class="panel panel-appmanager panel-case-actions">
  ..
</div>
```

```
<!-- B5 -->
<div class="card card-modern-gray mb-3 card-case-actions">
 ...
</div>
```

Pair with `card-modern-gray` (not a new `card-appmanager` class —
see [`panel-appmanager.md`](panel-appmanager.md)) and `mb-3` for
inter-card spacing. No `position-relative` utility.

### SCSS

```scss
.card-case-actions {
  background-color: lighten($cc-dark-cool-accent-hi, 3);

  > .card-header {
    background-color: $cc-dark-cool-accent-mid;
    color: white;

    .text-muted {
      // !important needed to beat B5's `.text-muted` utility class
      // (deprecated but still generated, with `color: ... !important`).
      color: $cc-dark-cool-accent-hi !important;
    }
  }
}
```
