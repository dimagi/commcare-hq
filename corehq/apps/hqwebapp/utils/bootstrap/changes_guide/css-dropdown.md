`dropdown` has been slightly refactored.

- `class="dropdown-item"` must now be added to `<ul class="dropdown-menu">` child links
- `data-toggle="dropdown"` is now `data-bs-toggle="dropdown"`
- any `<li class="divider"></li>` must now be `<li><hr class="dropdown-divider"></li>`
- dropdown toggles no longer require `<span class="caret"></span>`, you can now remove this

See: https://getbootstrap.com/docs/5.3/components/dropdowns/
