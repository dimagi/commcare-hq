The `nav` element has been restructured a bit so that you need to explicitly label
child elements with `nav-item` and `nav-link`.

An EXAMPLE for how to apply this change is provided below.
Please see docs for further details.

Previously:
```
<ul class="nav nav-tabs">
    <li class="active">
        <a href="#">Home</a>
    </li>
    <li>
        <a href="#">Profile</a>
    </li>
    <li>
        <a href="#">Messages</a>
    </li>
</ul>
```

Now:
```
<ul class="nav nav-tabs">
    <li class="nav-item active">
        <a class="nav-link active" aria-current="page" href="#">Home</a>
    </li>
    <li class="nav-item">
        <a class="nav-link" href="#">Profile</a>
    </li>
    <li class="nav-item">
        <a class="nav-link" href="#">Messages</a>
    </li>
</ul>
```

See: https://getbootstrap.com/docs/5.3/components/navs-tabs/#base-nav
