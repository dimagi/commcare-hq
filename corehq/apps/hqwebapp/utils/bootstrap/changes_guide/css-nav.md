B5 restructured navs: classes that lived on `<li>` (`active`, `disabled`)
move to the inner `<a>`, child elements need explicit `nav-item` /
`nav-link` classes, and several B3 layout classes have been dropped.

Four rules apply:

## 1. Add `nav-item` to `<li>` and `nav-link` to `<a>`

```
<!-- B3 -->
<li>
  <a href="#">
    Profile
  </a>
</li>
```

```
<!-- B5 -->
<li class="nav-item">
  <a class="nav-link" href="#">
    Profile
  </a>
</li>
```

## 2. Active state moves from `<li>` to `<a>` and gains `aria-current`

```
<!-- B3 -->
<li class="active">
  <a href="#">Home</a>
</li>
```

```
<!-- B5 -->
<li class="nav-item">
  <a class="nav-link active" aria-current"page" href="#">Home</a>
</li>
```

If the nav uses `data-bs-toggle="tab"` (or `pill`), Bootstrap manages the
active class itself — no static markup is needed.

## 3. Disabled state moves from `<li>` to `<a>` and gains `aria-disabled`

`disabled` on `<li>` is a no-op in B5. Move it onto the link and announce
the state to screen readers.

```
<!-- B3 -->
<li class="disabled">
  <a href="#">Coming soon</a>
</li>
```

```
<!-- B5 -->
<li class="nav-item">
  <a class="nav-link disabled" aria-disabled="true">Coming soon</a>
</li>
```

## 4. `nav-stacked` -> `flex-column`

`nav-stacked` doesn't exist in B5; use the `flex-column` utility on the
parent `<ul>` to make the nav vertical.

```
<!-- B3 -->
<ul class="nav nav-pills nav-stacked">
```

```
<!-- B5 -->
<ul class="nav nav-pills flex-column">
```

See: https://getbootstrap.com/docs/5.3/components/navs-tabs/#base-nav
