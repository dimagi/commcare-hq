Vellum
======

[![Build Status](https://travis-ci.org/dimagi/Vellum.svg?branch=master)](https://travis-ci.org/dimagi/Vellum)

Vellum is a JavaRosa [XForm](http://en.wikipedia.org/wiki/XForms) designer used
in [CommCare HQ](http://github.com/dimagi/commcare-hq).

![](http://i.imgur.com/PvrL8Rr.jpg)

Image courtesy of the [ReMIND
project](https://www.commcarehq.org/exchange/325775003aa58cfcefbc75cfdf132e4d/info/).

Vocabulary
----------

Some of the names used in the source code are less than intuitive. Hopefully
this list will help to reduce the confusion. The list is ordered with the least
intuitive items first.

- **Vellum**: also known as the _Form Builder_.
- **Mug**: an object representing a question. Each mug has a type: _Text_,
  _Date_, _Audio_, etc. While some mug type names match the corresponding label
  used in the UI, some do not. For example, a _Trigger_ is called a _Label_ in
  the UI.
- **JavaRosa**: the language/translation module. A core part of the JavaRosa
  module is the **IText** system, which provides an API for translated strings
  and multimedia used to adorn questions.
- **Widget**: a control or group of controls displayed on the right side of the
  screen and used to interact with mug properties.
- **Plugins**: features that are not part of the core are implemented as plugins.
  The plugin architecture is loosely based on the
  [JSTree](https://www.jstree.com/plugins/) plugin system. Many very important
  components are implemented as plugins, so just because something is a plugin
  does not mean it is a second-rate feature.

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
[here](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/app_manager/templates/app_manager/v1/form_designer.html)
and `tests/main.js` for example options usage.

Vellum targets modern browsers.  IE8 and earlier are not supported.

Tests
-----

Make sure everything is up to date:

```
$ bower update
$ npm update
```

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
grunt test --grep="test grep"
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
