`breadcrumb` has been rewritten. Most notably, `breadcrumb-item`
is now required on child `li` elements.

An EXAMPLE for how to apply this change is provided below.
Please see docs for further details.

Previously:
```
<ol class="breadcrumb">
    <li><a href="#">Home</a></li>
    <li><a href="#">Library</a></li>
    <li class="active">Data</li>
</ol>
```

Now:
```
<nav aria-label="breadcrumb">
    <ol class="breadcrumb">
        <li class="breadcrumb-item"><a href="#">Home</a></li>
        <li class="breadcrumb-item"><a href="#">Library</a></li>
        <li class="breadcrumb-item active" aria-current="page">Data</li>
    </ol>
</nav>
```

See: https://getbootstrap.com/docs/5.3/components/breadcrumb/
