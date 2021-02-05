# Managing Dependencies

### Note on editing unmigrated javascript

You can tell whether or not a JavaScript module is compatible with RequireJS by looking at its `hqDefine` call.

RequireJS modules look like this, with all dependencies loaded as part of `hqDefine`:

```
hqDefine("my_app/js/my_file", ["knockout", "hqwebapp/js/initial_page_data"], function (ko, initialPageData) {
    var myObservable = ko.observable(initialPageData.get("thing"));
    ...
});
```

Non-RequireJS modules look like this, with no list and no function parameters. HQ modules are loaded using `hqImport` in the body, and third party libraries aren't declared at all, instead relying on globals:

```
hqDefine("my_app/js/my_file", function () {
    var myObservable = ko.observable(hqImport("hqwebapp/js/initial_page_data").get("thing"));
    ...
});
```

If you're working in a non-RequireJS js file, **do not** add that list and parameters unless you are intending to migrate the module. It's easy to introduce bugs that won't be visible until the module is used on a RequireJS page, and modules are harder to migrate when they have pre-existing bugs. See "troubleshooting" below if you're curious about the kinds of issues that crop up.
