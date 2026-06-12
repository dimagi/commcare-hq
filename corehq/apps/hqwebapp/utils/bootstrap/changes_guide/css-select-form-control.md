Replace `form-control` with `form-select` on `<select>` elements.

```
<!-- B3 -->
<select class="form-control">...</select>
```

```
<!-- B5 -->
<select class="form-select">...</select>
```
## Width: check for inline siblings

In B5, `form-select` defaults to `width: 100%`. So:

- If the select sits on a visual line with **sibling inline content**
  (a button, label fragment, another input) → **add `w-auto`** so it
  keeps content width and the siblings stay on the same line.
- If the select stands alone in its own row, card-body, or column →
  leave as `form-select`, full-width is appropriate.

```
<!-- inline context: select + button on same row -->
<select class="form-select w-auto">...</select>
<button class="btn btn-primary">Copy</button>
```

The B3 hint that a select needs `w-auto` is the parent having
`.form-inline` (or being a `<form class="form-inline">`). That class
disappears after css-form-inline migration, so prefer to do
css-select-form-control **before** css-form-inline — the parent class
is still grep-able as a signal.

## Verification: paired with css-form-inline

`form-inline` is a no-op in HQ's B5 stylesheets. So `w-auto` alone
won't restore horizontal "select + button" layout — the parent also
has to become a flex container, which is what css-form-inline does.

Verify the layout **after** css-form-inline is migrated, not after
css-select-form-control alone. In an intermediate state, the select
will have the right size but the layout will still stack vertically.
