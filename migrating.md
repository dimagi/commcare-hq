# Migrating

Modernizing our JavaScript code base often means doing migrations. Currently in progress is a migration of in-page `<script>` blocks to separate .js files, also called "externalizing" JavaScript. This page largely summarizes information from [Server Integration Patterns](./integration-patterns.md), organized to be useful to someone who is migrating an entire page of script blocks to external files.

Basic migration process:

1. Within each script block, replace any Django syntax with JavaScript equivalents
1. Move the script block contents to a file.
1. Add any new `<script>` tags to the page.

For the sanity of code reviewers, do step 1 in a separate commit that step 2.

Sample PRs:
- [Externalize JavaScript: Groups](https://github.com/dimagi/commcare-hq/pull/15553) is an example of migrating two straightforward entire pages: one that has inline JavaScript without any Django syntax, and a second that has inline JavaScript that uses some translations and initial page data.
- [Externalize JavaScript: more report filters](https://github.com/dimagi/commcare-hq/pull/17184/files) is an example of migrating a partial that defines a simple widget.

## Replacing Django syntax with JavaScript Equivalents

There are a couple of common use cases for using Django inside of JavaScript code.

### Translations

The `trans` template tag can be replaced with `gettext`, which is globally available:

```
var label = "{% trans "Danger"|escapejs %}";
```

becomes

```
var label = gettext("Danger");
```

See [Server Integration Patterns](./integration-patterns.md) for details.

### Passing server data to the client

This is a frequent pattern in legacy code:
```
var myThing = {{ thing }};
doStuff(myThing);
```

This can be avoided by using the `initial_page_data` template tag to register server data in the template:
```
{% initial_page_data 'myThing' thing %}
```

The data can then be accessed in JavaScript via `hqwebapp/js/initial_page_data`:
```
var myThing = hqImport('hqwebapp/js/initial_page_data').get('myThing');
doStuff(myThing);
```

See [Server Integration Patterns](./integration-patterns.md) for details.

### Generating URLs

This is a special case of passing server data to the client and is handled in a simliar fashion.

```
var url = "{% url "my_page" domain %}";
```

becomes

```
{% registerurl "my_page" domain %}
```

in the template and then is accessible to JavaScript:

```
var url = hqImport('hqwebapp/js/initial_page_data.js').reverse("my_page");
```

See [Server Integration Patterns](./integration-patterns.md) for details, including how to handle more dynamic URLs.

### Control flow

Control flow like `{% if %} ... {% endif %}` is generally straightforward to change to JavaScript; it usually exists because there's logic that depends on server-provided data.

### Angular

Although Angular is no longer used for new code, a handful of legacy angular pages remain. These use the [djng_current_rmi](http://django-angular.readthedocs.io/en/latest/remote-method-invocation.html) template tag to set up Angular's remote method invocation:
```
myApp.config(["djangoRMIProvider", function(djangoRMIProvider) {
   djangoRMIProvider.configure({% djng_current_rmi %});
}]);
```

We have the class [HQJSONResponseMixin](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/hqwebapp/views.py#L1262) to add `djng_current_rmi` to a view's base context. Templates can then register `djng_current_rmi` as initial page data and access it in JavaScript. See [7562ff3](https://github.com/dimagi/commcare-hq/commit/7562ff353877e3f6bf98695796ce147f1e2f7b46) for an example of replacing `{% djng_current_rmi %}` with `HQJSONResponseMixin`.

## Moving script block contents into a file

The most common and straightforward approach is to make a new js file that belongs to the page you're migrating. Sometimes, the page will already have such a file that you can just add to. Occasionally, it'll make sense to move code to a file shared by several pages, although this takes more thought and creating a new file is always a reasonable fallback.

It's often necessary to move interactive code (event handlers, knockout model initializations, etc.) into a [document ready handler](https://api.jquery.com/ready/) if it wasn't already in one. Note that we're on jQuery 3, so `$(...)` is the recommended document ready syntax.

## Adding any new script tags

This is straightforward: make sure every .js file you added to has a script tag in your page.

## Testing

It's often prohibitively time-consuming to test every JavaScript interaction on a page. However, it's always important to at least load the page to check for major errors. Beyond that, test for weak spots based on the changes you made:
- Added document ready handlers? Verify your code is getting called.
- Added initial page data? Verify it's being populated.
- Translated Django control flow to JavaScript? Verify the major code paths execute as expected.
- And so forth...
