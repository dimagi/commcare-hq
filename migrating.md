# Migrating

Modernizing our JavaScript code base often means doing migrations. Migrations currently in progress:
1. [Migrating to RequireJS](#migrating-to-requirejs)
1. [Moving away from classical inheritance](#moving-away-from-classical-inheritance)

## Migrating to RequireJS

- [Background: modules and pages](#background-modules-and-pages)
- [Basic Migration Process](#basic-migration-process)
- [Troubleshooting](#troubleshooting)

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

Considerations when choosing or creating a main module
- Most often, there's already a single script that's only included on the page you're migrating, which you can use as the main module.
- It's fine for multiple pages to use the same main module - this may make sense for closely related pages.
- Sometimes a page will have some dependencies but no page-specific logic, so you can make a main module with an empty body, as in [invoice_main.js](https://github.com/dimagi/commcare-hq/commit/d14ba14f13d7d44e3a96940d2c72d2a1b918534d#diff-b81a32d5fee6a9c8af07b189c6a5693e).
- Sometimes you can add a dependency or two to an existing module and then use it as your main module. This can work fine, but be cautious of adding bloat or creating dependencies between django apps. There's a loose hierarchy:
   - Major third-party libraries: jQuery, knockout, underscore
   - hqwebapp
   - analytics
   - app-specific reusable modules like [accounting/js/widgets](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/accounting/static/accounting/js/widgets.js), which are also sometimes used as main modules
   - page-specific modules like [accounting/js/subscriptions_main](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/accounting/static/accounting/js/subscriptions_main.js)
- There's a growing convention of using the suffix `_main` for main modules - more specifically, for any module that runs logic in a document ready handler.
- HTML files that are only used as the base for other templates don't need to have a main module or a `requirejs_main` tag.

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
- Check the template's parent template:
   - If the parent has a `requirejs_main` module, the template you're migrating should include a dependency on that module.
   - If the parent still has `<script>` tags, the template you're migrating should include those as dependencies. It's usually convenient to migrate the parent and any "sibling" templates at the same time so you can remove the `<script>` tags altogether. If that isn't possible, make the parent check before including script tags: `{% if requirejs_main %}<script ...></script>{% endif %}`
   - Also check the parent's parent template, etc. Stop once you get to `hqwebapp/base.html`, `hqwebapp/two_column.html`, or `hqwebapp/base_section.html`.

for `<script>` tags or `requirejs_main` modules. Any dependencies of the ancestors also need to be included in the template you're migrating
- Check the view for any [hqwebapp decorators](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/hqwebapp/decorators.py) like `use_jquery_ui` which are used to include many common yet not global third-party libraries. Note that you typically should **not** remove the decorator, because these decorators often control both css and js, but you **do** need to add any js scripts controlled by the decorator to your js module.
- If the module uses any globals from third parties, add the script as a dependency and also add the global to `thirdPartyGlobals` in [hqModules.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/hqwebapp/static/hqwebapp/js/hqModules.js) which prevents errors on pages that use your module but are not yet migrated to requirejs.

Dependencies that aren't directly referenced as modules **don't** need to be added as function parameters, but they **do** need to be in the dependency list, so just put them at the end of the list. This tends to happen for custom knockout bindings, which are referenced only in the HTML, or jQuery plugins, which are referenced via the jQuery object rather than by the module's name.

#### Test

It's often prohibitively time-consuming to test every JavaScript interaction on a page. However, it's always important to at least load the page to check for major errors. Beyond that, test for weak spots based on the changes you made:
- If you replaced any `hqImport` calls that were inside of event handlers or other callbacks, verify that those areas still work correctly. When a migrated module is used on an unmigrated page, its dependencies need to be available at the time the module is defined. This is a change from previous behavior, where the dependencies didn't need to be defined until `hqImport` first called them. We do not currently have a construct to require dependencies after a module is defined.
- The most likely missing dependencies are the invisible ones: knockout bindings and jquery plugins like select2. These often don't error but will look substantially different on the page if they haven't been initialized.
- If your page depends on any third-party modules that might not yet be used on any RequireJS pages, test them. Third-party modules sometimes need to be upgraded to be compatible with RequireJS.
- If your page touched any javascript modules that are used by pages that haven't yet been migrated, test at least one of those non-migrated pages.
- Check if your base template has any descendants that should also be migrated.

### Troubleshooting
TODO

## Moving away from classical inheritance

See [our approach to inheritance](https://github.com/dimagi/js-guide/blob/master/code-organization.md#inheritance). Most of our classical-style inheritance is a format than can be fairly mechanically changed to be functional:
- In the class definition, make sure the instance is initialized to an empty object instead of `this`. There's usually a `var self = this;` line that should be switched to `var self = {};`
- Throughout the class definition, make sure the code is consistently using `self` instead of `this`
- Make sure the class definition returns `self` at the end (typically it won't return anything)
- Update class name from `UpperCamelCase` to `lowerCamelCase`
- Remove `new` operator from anywhere the class is instantiated
- Sanity test that the pages using the class still load

[Sample pull request](https://github.com/dimagi/commcare-hq/pull/19938)

Code that actually manipulates the prototype needs more thought.
