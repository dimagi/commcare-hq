# Migrating

Modernizing our JavaScript code base often means doing migrations. Migrations currently in progress:
1. [Migrating to RequireJS](#migrating-to-requirejs)
1. [Moving away from classical inheritance](#moving-away-from-classical-inheritance)
1. [Upgrading Select2](#upgrading-select2)

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
   - Also check the parent's parent template, etc. Stop once you get to `hqwebapp/base.html`, `hqwebapp/two_column.html`, or `hqwebapp/base_section.html`, which already support requirejs.

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

#### Troubleshooting migration issues

When debugging RequireJS issues, the first question is whether or not the page you're on has been migrated. You can find out by checking the value of `window.USE_REQUIREJS` in the browser console.

Common issues on RequireJS pages:
- JS error like `$(...).something is not a function`: this indicates there's a missing dependency. Typically "something" is either `select2` or a jQuery UI widget like `datepicker`. To fix, add the missing dependency to the module that's erroring.
- Missing functionality, but no error: this usually indicates a missing knockout binding. To fix, add the file containing the binding to the module that applies that binding, which usually means adding `hqwebapp/js/knockout_bindings.ko` to the page's main module.
- JS error like `something is not defined` where `something` is one of the parameters in the module's main function: this can indicate a circular dependency. This is rare in HQ. Track down the circular dependency and see if it makes sense to eliminate it by reorganizing code. If it doesn't, you can use [hqRequire](https://github.com/dimagi/commcare-hq/commit/15b436f77875f57d1e3d8d6db9b990720fa5dd6f#diff-73c73327e873d0e5f5f4e17c3251a1ceR100) to require the necessary module at the point where it's used rather than at the top of the module using it.
- JS error like `x is not defined` where `x` is a third-party module, which is the dependency of another third party module `y` and both of them are non RequireJs modules. You may get this intermittent error when you want to use `y` in the migrated module and `x` and `y` does not support [AMD](https://requirejs.org/docs/whyamd.html). You can fix this using [shim](https://www.devbridge.com/articles/understanding-amd-requirejs#To-shim-or-not-to-shim) or [hqRequire](https://github.com/dimagi/commcare-hq/commit/15b436f77875f57d1e3d8d6db9b990720fa5dd6f#diff-73c73327e873d0e5f5f4e17c3251a1ceR100). [Example](https://github.com/dimagi/commcare-hq/pull/21604/files#diff-cf0be09b7db821551ac73dc3a9829e5eR24) of this could be `d3` and `nvd3`

Common issues on non-RequireJS pages:
- JS error like `something is not defined` where `something` is a third-party module: this can happen if a non-RequireJS page uses a RequireJS module which uses a third party module based on a global variable. There's some code that mimicks RequireJS in this situation, but it needs to know about all of the third party libraries. To fix, add the third party module's global to [thirdPartyMap in hqModules.js](https://github.com/dimagi/commcare-hq/commit/85286460a8b08812f82d6709c161b259e77165c4#diff-73c73327e873d0e5f5f4e17c3251a1ceR57).
- JS error like `something is not defined` where `something` is an HQ module: this can happen when script tags are ordered so that a module appears before one of its dependencies. This can happen to migrated modules because one of the effects of the migration is to typically import all of a module's dependencies at the time the module is defined, which in a non-RequireJS context means all of the dependencies' script tags must appear before the script tags that depend on them. Previously, dependencies were not imported until `hqImport` was called, which could be later on, possibly in an event handler or some other code that would never execute until the entire page was loaded. To fix, try reordering the script tags. If you find there's a circular dependency, use `hqRequire` as described above.

#### Troubleshooting the RequireJS build process

Tactics that can help track down problems with the RequireJS build process, which usually manifest as errors that happen on staging but not locally:

- To turn off minification, you can run `build_requirejs` with the `--no_optimize` option. This also makes the script run much faster.
- To stop using the CDN, comment out [resource_versions.js in hqwebapp/base.html](https://github.com/dimagi/commcare-hq/pull/18116/files#diff-1ecb20ffccb745a5c0fc279837215a25R433). Note that this will still fetch a few files, such as `hqModules.js` and `requirejs_config.js`, from the CDN. To turn off the CDN entirely, comment out all of the code that manipulates `resource_versions` in [build_requirejs](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/hqwebapp/management/commands/build_requirejs.py).
- To mimic the entire build process locally:
   - Collect static files: `manage.py collectstatic --noinput`  This is necessary if you've made any changes to `requirejs.yaml` or `requirejs_config.js`, since the build script pulls these files from `staticfiles`, not `corehq`.
   - Compile translation files: `manage.py compilejsi18n`
   - Run the build script: `manage.py build_requirejs --local`
      - This will **overwrite** your local versions of `requirejs_config.js` and `resource_versions.js`, so be cautious running it if you have uncommitted changes.
      - This will also copy the generated bundle files from `staticfiles` back into `corehq`.
      - If you don't need to test locally but just want to see the results of dependency tracing, leave off the `--local`. A list of each bundle's contents will be written to `staticfiles/build.txt`, but no files will be added to or overwritten in `corehq`.

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

## Upgrading Select2

HQ uses two different versions of select2. We're in the process of upgrading usage of the old version,
because in principle it's crazy to have two versions but also because practically, having multiple versions
makes it harder to bundle and share code across pages effectively.

|                | New Select2                        | Old Select2                       |
| -------------- | ---------------------------------- | --------------------------------- |
| Version        |  4.0.0                             | 3.5.2                             |
| Docs           | https://select2.org/               | http://select2.github.io/select2/ |
| JS module      | `select2/dist/js/select2.full.min` | `select2-3.5.2-legacy/select2`    |
| View decorator | none                               | `@use_select2_legacy`             |

This is a fairly complicated migration both because the old and new version differ in multiple significant ways and because of how code is shared in HQ.

### Figuring out what to migrate

Migrating one select2 widget typically leads to migrating a number of other dependent ones. There are a couple of ways to pick a starting point:

- Pick a view that uses the `use_select2_legacy` decorator
- Pick a javascript module that directly depends on `select2-3.5.2-legacy/select2`
- Pick a page that includes a script tag for `select2-3.5.2-legacy/select2.js` (rare, because most pages use the `@use_select2_legacy` decorator rather than including a script tag)
- Browse the [requirejs bundle configuration](https://www.commcarehq.org/static/build.txt) to find modules that indirectly depend on `select2-3.5.2-legacy/select2`
- Javascript modules that don't yet declare dependencies but that call the `.select2()` function
- Pages that use a select2-dependent knockout binding like `select2`, `autocompleteSelect2`, or `questionsSelect`

### Migrating

The two versions of select2 have several types of differences.

- Javascript: the new API has numerous differences. There are several select2-heavy javascript modules that have both an old and new version, so it can be helpful to look for javascript filenames ending `v3.js` and the corresponding files ending in `v4.js` to see how the API has changed. Changes frequently needed in HQ code:
   - `formatResult` and `formatSelection` have been renamed to `templateResult` and `templateSelection`
   - The `results` option for ajax is renamed to `processResults`
   - `placeholder` is now required if `allowClear` is true (set it to `' '` if there isn't placeholder text)
   - `formatNoMatches` text for when there are no results is now part of the `language` option
      - v3 `formatNoMatches: function() { return gettext("No groups found"); }`
      - v4 `language: { noResults: { return gettext("No groups found"); } }`
   - The `data` option for ajax now takes a `params` parameter with a `term` property instead of having `term` passed as a parameter
      - v3 `data: fuction (term) { return { query: term }; }`
      - v4 `data: function (params) { return { query: params.term } }`
   - To allow freetext entry, instead of using `createSearchChoice`, set `tags` to true. Custom logic relating to creating new options (such as validation for email inputs) can be added using `createTag`.
   - To allow for HTML in custom option templates, set `escapeMarkup` to a pass-through function: `function (m) { return m; }`
   - `initSelection` to initially populate the selected value is deprecated. Instead, you must make sure any selected options are added to the `<select>` element and then call `$element.val(...)` to set the value. Note that you also need to trigger a change event for the value to appear in the UI, and that you can trigger a `change.select2` instead of `change` if you don't want that event to be picked up by other code.
   - To programmatically update a select2 value, you used to call `$el.select2('val', newValue)` but can now call `$el.val(newValue)` (again triggering a `change` event to make this visible in the UI.
- HTML: the element underlying the select2 now has to be a `<select>`. Most of our old code uses text inputs. This typically means making one of two changes:
   - For handwritten HTML, change the element type.
   - For crispy forms, update the underlying field's widget. Most often this means taking a field like `forms.CharField(label=ugettext_lazy('Thing'))` and adding a `widget=forms.Select(choices=[])` param (or `SelectMultiple`). This can get more complicated when you're dealing with a multiselect (continue reading)
- Saving multiselects: Multiselects now express their values as arrays of strings, whereas they used to be a single comma-separated string. This can mean updating javascript and also form saving code in python. See the [upgrade of domain pages](https://github.com/dimagi/commcare-hq/pull/22971/) for examples of updating form cleaning and saving code.

Reference PRs:
- [Form view](https://github.com/dimagi/commcare-hq/pull/22906)
- [Locations](https://github.com/dimagi/commcare-hq/pull/21797)
- [Domain pages](https://github.com/dimagi/commcare-hq/pull/22971)
- [Accounting](https://github.com/dimagi/commcare-hq/pull/23030)

### Figuring out what else you now have to migrate

- A single page can only use one version of select2, so all instances on the page need to be migrated.
- If you changed any python, most likely a form, any other pages using that form also likely need to be migrated.
- If you're working on a requirejs page, you need to migrate the entire bundle. A bundle that contains both versions of select2 will throw javascript errors. There's a test to check for this, which you can also run manually: `corehq.apps.hqwebapp.tests.test_requirejs:TestRequireJSBuild.test_no_select2_conflicts`

### Testing

Test that
- Your page loads without javascript errors
- You form saves properly
- Your form displays existing values properly (this often breaks, because of the new requirement that any initial values need to be options in the select)
- If dealing with a multiselect, try saving one value, multiple values, and no values
