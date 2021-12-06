# Third-Party Libraries

This page discusses when to use the major, UI-framework-level, libraries we depend on, along with a few common code
conventions for these libraries.

## jQuery
[jQuery](https://jquery.com/) is available throughout HQ. We use jQuery 3.

Prefix jQuery variables with a `$`:
```
var $rows = $("#myTable tr"),
    firstRow = $rows[0];
```

## Underscore
[Underscore](http://underscorejs.org/) is available throughout HQ for utilities.

## Knockout
[Knockout](http://knockoutjs.com/) is also available throughout HQ and should be used for new code. We use Knockout 3.0.

Prefix knockout observables with an `o`:

```
var myModel = function (options) {
    var self = this;
    self.type = options.type;
    self.oTotal = ko.observable(0);
};
```

...so that in HTML it's apparent what you're dealing with:

```
<input data-bind="visible: type === 'large' && oTotal() > 10, value: oTotal" />

Current total: <span data-bind="text: oTotal"></div>
```

## Backbone and Marionette
[Backbone](http://backbonejs.org/) is used in Web Apps. It **should not** be used outside of Web Apps. Within Web
Apps, we use [Marionette](http://marionettejs.com/) for most UI management.

## Yarn
We use [yarn](https://classic.yarnpkg.com/en/) for package management, so new libraries should be added to [package.json](https://github.com/dimagi/commcare-hq/blob/master/package.json).
