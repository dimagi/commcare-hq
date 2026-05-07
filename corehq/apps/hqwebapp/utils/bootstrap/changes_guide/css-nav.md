B5 restructured navs: classes that lived on `<li>` (`active`, `disabled`)
move to the inner `<a>`, child elements need explicit `nav-item` /
`nav-link` classes, and several B3 layout classes have been dropped.

Four rules apply:

## 1. Add `nav-item` to `<li>` and `nav-link` to `<a>`

```
<!-- B3 -->            <!-- B5 -->
<li>                   <li class="nav-item">
  <a href="#">           <a class="nav-link" href="#">
    Profile                Profile
  </a>                   </a>
</li>                  </li>
```

## 2. Active state moves from `<li>` to `<a>` and gains `aria-current`

```
<!-- B3 -->                 <!-- B5 -->
<li class="active">         <li class="nav-item">
  <a href="#">Home</a>        <a class="nav-link active" aria-current="page" href="#">Home</a>
</li>                       </li>
```

If the nav uses `data-bs-toggle="tab"` (or `pill`), Bootstrap manages the
active class itself — no static markup is needed.

## 3. Disabled state moves from `<li>` to `<a>` and gains `aria-disabled`

`disabled` on `<li>` is a no-op in B5. Move it onto the link and announce
the state to screen readers.

```
<!-- B3 -->                            <!-- B5 -->
<li class="disabled">                  <li class="nav-item">
  <a href="#">Coming soon</a>            <a class="nav-link disabled" aria-disabled="true">Coming soon</a>
</li>                                  </li>
```

## 4. `nav-stacked` -> `flex-column`

`nav-stacked` doesn't exist in B5; use the `flex-column` utility on the
parent `<ul>` to make the nav vertical.

```
<!-- B3 -->                                       <!-- B5 -->
<ul class="nav nav-pills nav-stacked">            <ul class="nav nav-pills flex-column">
```

See: https://getbootstrap.com/docs/5.3/components/navs-tabs/#base-nav
