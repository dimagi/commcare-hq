`dropdown` has been slightly refactored.

- `class="dropdown-item"` must now be added to `<ul class="dropdown-menu">` child links
- `data-toggle="dropdown"` is now `data-bs-toggle="dropdown"`
- any `<li class="divider"></li>` must now be `<li><hr class="dropdown-divider"></li>`
- any `<li class="dropdown-header">` must now be a heading element with `class="dropdown-header"` (B5 expects an `<h*>`, not `<li>`). Pick the level that fits the page's heading outline — Bootstrap's example uses `<h6>`, which usually fits since dropdowns sit deep in the hierarchy.
- `dropdown-menu-right` is renamed to `dropdown-menu-end` (B5 uses logical-property naming for RTL support; same for `dropdown-menu-left` → `dropdown-menu-start`)
- dropdown toggles no longer require `<span class="caret"></span>`, you can now remove this

See: https://getbootstrap.com/docs/5.3/components/dropdowns/

### Gotcha: false-positive markers

The auto-renamer flags any line containing the word "dropdown" (regex matches it surrounded by whitespace/quotes/braces). HTML comments like `<!-- ... a dropdown -->` will pick up a spurious `{# todo B5: css-dropdown #}` marker. If you see the marker on a `<select>` element or in an HTML comment, just remove the marker — no migration needed.
