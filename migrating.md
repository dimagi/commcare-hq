# Migrating

Modernizing our JavaScript code base often means doing migrations. Two migrations are currently in progress:
1. Moving in-page `<script>` blocks to separate .js files, also called "externalizing" JavaScript. 
1. Migrating to RequireJS

## Migrating inline script blocks to js files
This page largely summarizes information from [Server Integration Patterns](./integration-patterns.md), organized to be useful to someone who is migrating an entire page of script blocks to external files.

Basic migration process:

1. Within each script block, replace any Django syntax with JavaScript equivalents
1. Move the script block contents to a file.
1. Add any new `<script>` tags to the page.

For the sanity of code reviewers, do step 1 in a separate commit that step 2.

Sample PRs:
- [Externalize JavaScript: Groups](https://github.com/dimagi/commcare-hq/pull/15553) is an example of migrating two straightforward entire pages: one that has inline JavaScript without any Django syntax, and a second that has inline JavaScript that uses some translations and initial page data.
- [Externalize JavaScript: more report filters](https://github.com/dimagi/commcare-hq/pull/17184/files) is an example of migrating a partial that defines a simple widget.

### Replacing Django syntax with JavaScript Equivalents

There are a couple of common use cases for using Django inside of JavaScript code.

#### Translations

The `trans` template tag can be replaced with `gettext`, which is globally available:

```
var label = "{% trans "Danger"|escapejs %}";
```

becomes

```
var label = gettext("Danger");
```

See [Server Integration Patterns](./integration-patterns.md) for details.

#### Passing server data to the client

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

#### Generating URLs

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

#### Control flow

Control flow like `{% if %} ... {% endif %}` is generally straightforward to change to JavaScript; it usually exists because there's logic that depends on server-provided data.

#### Angular

Although Angular is no longer used for new code, a handful of legacy angular pages remain. These use the [djng_current_rmi](http://django-angular.readthedocs.io/en/latest/remote-method-invocation.html) template tag to set up Angular's remote method invocation:
```
myApp.config(["djangoRMIProvider", function(djangoRMIProvider) {
   djangoRMIProvider.configure({% djng_current_rmi %});
}]);
```

We have the class [HQJSONResponseMixin](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/hqwebapp/views.py#L1262) to add `djng_current_rmi` to a view's base context. Templates can then register `djng_current_rmi` as initial page data and access it in JavaScript. See [7562ff3](https://github.com/dimagi/commcare-hq/commit/7562ff353877e3f6bf98695796ce147f1e2f7b46) for an example of replacing `{% djng_current_rmi %}` with `HQJSONResponseMixin`.

### Moving script block contents into a file

The most common and straightforward approach is to make a new js file that belongs to the page you're migrating. Sometimes, the page will already have such a file that you can just add to. Occasionally, it'll make sense to move code to a file shared by several pages, although this takes more thought and creating a new file is always a reasonable fallback.

If you're creating a new file, make it an [hqDefine](https://github.com/dimagi/js-guide/blob/master/code-organization.md#hqdefine) module. As long as the code you're moving doesn't rely on global variables, this should be a nearly trivial change.

It's often necessary to move interactive code (event handlers, knockout model initializations, etc.) into a [document ready handler](https://api.jquery.com/ready/) if it wasn't already in one. Note that we're on jQuery 3, so `$(...)` is the recommended document ready syntax.

### Adding any new script tags

This is straightforward: make sure every .js file you added to has a script tag in your page.

### Testing

It's often prohibitively time-consuming to test every JavaScript interaction on a page. However, it's always important to at least load the page to check for major errors. Beyond that, test for weak spots based on the changes you made:
- Added document ready handlers? Verify your code is getting called.
- Added initial page data? Verify it's being populated.
- Translated Django control flow to JavaScript? Verify the major code paths execute as expected.
- And so forth...

## Migrating to RequireJS (DRAFT)

### Background: modules and pages

The RequireJS migration deals with both **pages** (HTML) and **modules** (JavaScript). Any individual page is either migrated or not. Individual modules are also migrated or not, but a "migrated" module may be used on both RequireJS and non-RequireJS pages.

Logic in `hqModules.js` determines whether or not we're in a RequireJS environment and changes the behavior of `hqDefine` accordingly. In a RequireJS environment, `hqDefine` just passes through to RequireJS's `define`. Once all pages have been migrated, we'll be able to delete `hqModules.js` altogether and switch all of the `hqDefine` calls to `define`.

These docs walk through the process of migrating a single page to RequireJS.

### Basic Migration Process

Prerequisites: Before a page can be migrated, **all** of its dependencies must already be in external JavaScript files and must be using `hqDefine`. See above for details on moving inline script blocks to files, and see [module patterns](https://github.com/dimagi/js-guide/blob/master/code-organization.md#module-patterns) for details on `hqDefine`. Also, pages that are not descendants of [hqwebapp/base.html](https://github.com/dimagi/commcare-hq/tree/master/corehq/apps/hqwebapp/templates/hqwebapp/base.html) cannot yet be migrated.

Once these conditions are met, migrating to RequireJS is essentially the process of explicitly adding each module's dependencies to the module's definition, and also updating each HTML page to reference a single "main" module rather than including a bunch of `<script>` tags:
1. Add `requirejs_main` tag and remove `<script>` tags
1. Add dependencies
1. Test

Sample PRs:
- [RequireJS migration: dashboard](https://github.com/dimagi/commcare-hq/pull/19182/) is an example of an easy migration, where all dependencies are already migrated
- [RequireJS proof of concept](https://github.com/dimagi/commcare-hq/pull/18116) migrates a few pages (lookup tables, data dictionary) and many of our commonly-used modules (analytics, `hq.helpers.js`, etc.). This also contains the changes to `hqModules.js` that make `hqDefine` support both migrated and unmigrated pages.

#### Add `requirejs_main` tag and remove `<script>` tags

The `requirejs_main` tag is what indicates that a page should use RequireJS. The page should have one "main" module. Most of our pages are already set up like this: they might include a bunch of scripts, but there's one in particular that handles the event handlers, bindings, etc. that are specific to that page.

It's fine for multiple pages to use the same main module - this may make sense for closely related pages.

Add `{% requirejs_main 'myApp/js/myModule' %}` near the top of the template: it can go after `load` and `extends` but should appear before content blocks. Note that it's a module name, not a file name, so it doesn't include `.js`.

Remove other `<script>` tags from the file. You'll be adding these as dependencies to the main module.

#### Add dependencies

In your main module, add any dependent modules. Pre-RequireJS, a module definition looks like this:
```
hqDefine("app/js/utils", function() {
   var $this = $("#thing");
   hqImport("otherApp/js/utils").doSomething($thing);
   ...
});
```
The migrated module will have its dependencies passed as an array to `hqDefine`, and those dependencies will become parameters to the module's encompassing function:
```
hqDefine("app/js/utils", [
   "jquery",
   "otherApp/js/utils"
], function(
   $,
   otherUtils
) {
   var $this = $("#thing");
   otherUtils.doSomething($thing);
   ...
});
```
To declare dependencies:
- Check if the module uses jQuery, underscore, or knockout, and if so add them (their module names are all lowercase: 'jquery', 'knockout', 'underscore').
- Search the module for `hqImport` calls. Add any imported modules do the dependency list and parameter list, and replace calls to `hqImport(...)` with the new parameter name.
- If you removed any `<script>` tags from the template and haven't yet added them to the dependency list, do that.
- Check the view for any [hqwebapp decorators](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/hqwebapp/decorators.py) like `use_jquery_ui` which are used to include many common yet not global third-party libraries.

Dependencies that aren't directly referenced as modules **don't** need to be added as function parameters, but they **do** need to be in the dependency list, so just put them at the end of the list. This tends to happen for custom knockout bindings, which are referenced only in the HTML, or jQuery plugins, which are referenced via the jQuery object rather than by the module's name.

#### Test

It's often prohibitively time-consuming to test every JavaScript interaction on a page. However, it's always important to at least load the page to check for major errors. Beyond that, test for weak spots based on the changes you made:
- If you replaced any `hqImport` calls that were inside of event handlers or other callbacks, verify that those areas still work correctly. When a migrated module is used on an unmigrated page, its dependencies need to be available at the time the module is defined. This is a change from previous behavior, where the dependencies didn't need to be defined until `hqImport` first called them. We do not currently have a construct to require dependencies after a module is defined.
- The most likely missing dependencies are the invisible ones: knockout bindings and jquery plugins like select2. These often don't error but will look substantially different on the page if they haven't been initialized.
- If your page depends on any third-party modules that might not yet be used on any RequireJS pages, test them. Third-party modules sometimes need to be upgraded to be compatible with RequireJS.
