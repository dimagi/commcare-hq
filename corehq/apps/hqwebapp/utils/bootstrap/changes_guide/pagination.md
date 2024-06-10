`pagination` has been rewritten. Most notably, `page-item` and `page-link` are now
required on child `li` and links.

An EXAMPLE for how to apply this change is provided below.
Please see docs for further details.

Previously:
```
<nav aria-label="Page navigation">
    <ul class="pagination">
        <li>
            <a href="#" aria-label="Previous">
                <span aria-hidden="true">&laquo;</span>
            </a>
        </li>
        <li><a href="#">1</a></li>
        ...
    </ul>
</nav>
```

Now:
```
<nav aria-label="Page navigation example">
    <ul class="pagination">
        <li class="page-item"><a class="page-link" href="#">Previous</a></li>
        <li class="page-item"><a class="page-link" href="#">1</a></li>
        ...
    </ul>
</nav
```

See: https://getbootstrap.com/docs/5.3/components/pagination/
