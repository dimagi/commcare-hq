Vellum
======

[![Build Status](https://travis-ci.org/dimagi/Vellum.svg?branch=master)](https://travis-ci.org/dimagi/Vellum)

Vellum is a JavaRosa [XForm](http://en.wikipedia.org/wiki/XForms) designer used
in [CommCare HQ](http://github.com/dimagi/commcare-hq).

![](http://i.imgur.com/Eoi3XE3.png)

Image courtesy of the [ReMIND
project](https://www.commcarehq.org/exchange/325775003aa58cfcefbc75cfdf132e4d/info/).

Usage
-----

Checkout the source from [GitHub](https://github.com/dimagi/Vellum)

Optionally, build an optimized version

```sh
$ make # artifacts will be in _build dir and also vellum.tar.gz
```

Then load it on a page using [RequireJS](http://requirejs.org), optionally with
an existing jQuery instance:

```html
<link rel="stylesheet" href="path/to/bootstrap.css"></link>
<link rel="stylesheet" href="path/to/vellum/style.css"></link>
<!-- optional, if using bundled jquery et al -->
<link rel="stylesheet" href="path/to/vellum/global-deps.css"></link>

<!-- 
Optionally reuse existing jQuery instance with Bootstrap.  
If not present, bundled versions will be loaded.  -->
<script src="jquery.js"></script>
<script src="bootstrap.js"></script>

<script src="require.js"></script>
<script>
    require.config({
        packages: [
            {
                name: 'jquery.vellum',
                location: "/path/to/vellum/src"
            }
        ]
    });

    require(["jquery.vellum"], function () {
        require(["jquery"], function ($) {
            $(function () {
                $('#some_div').vellum(VELLUM_OPTIONS);
            });
        });
    });
</script>
```

See
[here](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/app_manager/templates/app_manager/form_designer.html)
and `tests/main.js` for example options usage.

Vellum targets modern browsers.  IE8 and earlier are not supported.

Tests
-----

Test in a browser:
```
$ `npm bin`/http-server -c-1
$ chromium-browser http://localhost:8080
```

By default, the test page will load the non-built version unless a `built`
parameter is present in the query string.

Commands to run tests headlessly:
```
grunt test
grunt test --grep "test grep"
```

You can also use `grunt watch` to test as file changes happen.

Contributing
------------

Follow the [Airbnb JavaScript Style Guide](https://github.com/airbnb/javascript).

Install dependencies:
```
$ npm install
```

Build optimized version (test locally by changing `useBuilt` in `tests/main.js`):
```
$ make
```
