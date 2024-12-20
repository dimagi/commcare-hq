JS Bundler Migration Guide
===========================

This page is a guide to upgrading legacy code in HQ to use Webpack, a modern JavaScript bundler.
Previously, we were migrating legacy code to RequireJS, an older JavaScript bundler which has since been
deprecated. If you wish to migrate a RequireJS page to Webpack, please see the `RequireJS to Webpack Migration Guide
<https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/requirejs-to-webpack.rst>`__

For information on how to work within existing code, see `Managing
Dependencies <https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/dependencies.rst>`__.
Both that page and `Historical Background on Module
Patterns <https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/module-history.rst>`__
are useful background for this guide.

-  `Background: modules and pages <#background-modules-and-pages>`__
-  `Basic Migration Process <#basic-migration-process>`__
-  `Troubleshooting <#troubleshooting>`__

Background: modules and pages
-----------------------------

The JS Bundler migration deals with both **pages** (HTML) and **modules**
(JavaScript). Any individual page is either migrated or not. Individual
modules are also migrated or not, but a “migrated” module may be used on
both bundled (Webpack and RequireJS) and non-bundled pages.

Logic in ``hqModules.js`` determines whether or not we’re in a bundler
environment (Webpack or RequireJS) and changes the behavior of
``hqDefine`` accordingly. In a bundler environment, ``hqDefine`` just passes
through to the standard AMD Module ``define``, which is understood by
both Webpack and RequireJS as a module and bundled accordingly.
Once all pages have been migrated, we’ll be able to delete
``hqModules.js`` altogether and switch all of the ``hqDefine`` calls to
``define``--or better, switch to using ES Modules (ESM).

These docs walk through the process of migrating a single page to
from not using a JavaScript bundler to using Webpack.

Basic Migration Process
-----------------------

Prerequisites: Before a page can be migrated, **all** of its
dependencies must already be in external JavaScript files and must be
using ``hqDefine``. This is already true for the vast majority of code
in HQ. Pages that are not descendants of
`hqwebapp/base.html <https://github.com/dimagi/commcare-hq/tree/master/corehq/apps/hqwebapp/templates/hqwebapp/base.html>`__,
which are rare, cannot yet be migrated.

Once these conditions are met, migrating to Webpack is essentially the
process of explicitly adding each module’s dependencies to the module’s
definition, and also updating each HTML page to reference a single
“main” module rather than including a bunch of ``<script>`` tags: 1. Add
``js_entry`` tag and remove ``<script>`` tags 1. Add dependencies
1. Test

.. note::
    The sample PRs below were created when we were still using RequireJS.
    You can read the sample PRs and substitute ``js_entry`` where you see
    ``requirejs_main``. Additionally, you should be sure to include the ``commcarehq``
    module in the list of dependencies of the final ``hqDefine`` entry point.

    See the `RequireJS to Webpack Migration Guide
    <https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/requirejs-to-webpack.rst>`__
    for additional guidance.


Sample PRs: - `Bundler migration (RequireJS):
dashboard <https://github.com/dimagi/commcare-hq/pull/19182/>`__ is an
example of an easy migration, where all dependencies are already
migrated - `Bundler proof of
concept (with RequireJS) <https://github.com/dimagi/commcare-hq/pull/18116>`__ migrates a
few pages (lookup tables, data dictionary) and many of our commonly-used
modules (analytics, ``hq.helpers.js``, etc.). This also contains the
changes to ``hqModules.js`` that make ``hqDefine`` support both migrated
and unmigrated pages.

Add ``js_entry`` tag and remove ``<script>`` tags
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``js_entry`` tag is what indicates that a page should use
Webpack. The page should have one "main" module, referred to as an Entry Point.
Most of our pages are already set up like this: they might include a bunch of scripts, but
there's one in particular that handles the event handlers, bindings,
etc. that are specific to that page. That script is the Entry Point.

Considerations when choosing or creating an Entry Point

- Most often, there's already a single script that's only included on the page you're
  migrating, which you can use as the entry point.
- It's fine for multiple pages to use the same entry point
  - this may make sense for closely related pages.
- Sometimes a page will have some dependencies
  but no page-specific logic, so you can make an entry point with an empty body, as in
  `invoice_main.js <https://github.com/dimagi/commcare-hq/commit/d14ba14f13d7d44e3a96940d2c72d2a1b918534d#diff-b81a32d5fee6a9c8af07b189c6a5693e>`__.
- Sometimes you can add a dependency or two to an existing module and
  then use it as your entry point. This can work fine, but be cautious of
  adding bloat or creating dependencies between django apps. There’s a
  loose hierarchy:

  - Major third-party libraries: jQuery, knockout, underscore
  - hqwebapp
  - analytics
  - app-specific reusable modules like `accounting/js/widgets <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/accounting/static/accounting/js/widgets.js>`__, which are also sometimes used as entry points
  - page-specific modules like `accounting/js/subscriptions_main <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/accounting/static/accounting/js/subscriptions_main.js>`__
- There's a growing convention of using the suffix ``_main`` for entry points - more specifically, for any module that runs logic in a document ready handler.
- HTML files that are only used as the base for other templates don't need to have a entry point or a ``js_entry`` tag.

Add ``{% js_entry "myApp/js/my_module" %}`` near the top of the
template: it can go after ``load`` and ``extends`` but should appear
before content blocks. Note that it’s a module name, not a file name, so
it doesn’t include ``.js``.

Remove other ``<script>`` tags from the file. You’ll be adding these as
dependencies to the entry point.

Add dependencies
~~~~~~~~~~~~~~~~

In your entry point, add any dependent modules. Pre-bundler, a module
definition looks like this:

::

   hqDefine("app/js/utils", function() {
      var $this = $("#thing");
      hqImport("otherApp/js/utils").doSomething($thing);
      ...
   });

The migrated module will have its dependencies passed as an array to
``hqDefine``, and those dependencies will become parameters to the
module’s encompassing function:

::

   hqDefine("app/js/utils", [
      "jquery",
      "otherApp/js/utils",
      "commcarehq"  // REQUIRED: always list this module that imports all site-level dependencies
                    // This can be at the end of the list.
   ], function(
      $,
      otherUtils
   ) {
      var $this = $("#thing");
      otherUtils.doSomething($thing);
      ...
   });

To declare dependencies:

- Check if the module uses jQuery, underscore, or knockout, and if so add them (their module names are all lowercase: ‘jquery’, ‘knockout’, ‘underscore’).
- Search the module for ``hqImport`` calls. Add any imported modules do the dependency list and
  parameter list, and replace calls to ``hqImport(...)`` with the new parameter name.
- If you removed any ``<script>`` tags from the template
  and haven’t yet added them to the dependency list, do that.
- Check the template’s parent template
    - If the parent has a ``js_entry`` module, the template you’re migrating should include a dependency on that module.
       - If the parent still has ``<script>`` tags, the template
         you’re migrating should include those as dependencies. It’s usually
         convenient to migrate the parent and any “sibling” templates at the same
         time so you can remove the ``<script>`` tags altogether. If that isn’t
         possible, make the parent check before including script tags:
         ``{% if js_entry %}<script ...></script>{% endif %}``
       - Also check the parent’s parent template, etc. Stop once you get to
         ``hqwebapp/base.html``, ``hqwebapp/bootstrap5/two_column.html``, or
         ``hqwebapp/bootstrap5/base_section.html``, which already support a bundler.
-  Check the view for any `hqwebapp
   decorators <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/hqwebapp/decorators.py>`__
   like ``use_jquery_ui`` which are used to include many common yet not
   global third-party libraries. Note that you typically should **not**
   remove the decorator, because these decorators often control both css
   and js, but you **do** need to add any js scripts controlled by the
   decorator to your js module.
-  If the module uses any globals from third parties, add the script as
   a dependency and also add the global to ``thirdPartyGlobals`` in
   `hqModules.js <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/hqwebapp/static/hqwebapp/js/hqModules.js>`__
   which prevents errors on pages that use your module but are not yet
   migrated to Webpack.

Dependencies that aren’t directly referenced as modules **don’t** need
to be added as function parameters, but they **do** need to be in the
dependency list, so just put them at the end of the list. This tends to
happen for custom knockout bindings, which are referenced only in the
HTML, or jQuery plugins, which are referenced via the jQuery object
rather than by the module’s name.

Test
~~~~

It’s often prohibitively time-consuming to test every JavaScript
interaction on a page. However, it’s always important to at least load
the page to check for major errors. Beyond that, test for weak spots
based on the changes you made:

- If you replaced any ``hqImport`` calls
  that were inside of event handlers or other callbacks, verify that those
  areas still work correctly. When a migrated module is used on an
  un-migrated page, its dependencies need to be available at the time the
  module is defined. This is a change from previous behavior, where the
  dependencies didn't need to be defined until ``hqImport`` first called
  them. We do not currently have a construct to require dependencies after
  a module is defined.
- The most likely missing dependencies are the
  invisible ones: knockout bindings and jquery plugins like select2. These
  often don’t error but will look substantially different on the page if
  they haven’t been initialized.
- If your page depends on any third-party
  modules that might not yet be used on any Webpack pages, test them.
  Third-party modules sometimes need to be upgraded to be compatible with Webpack
  or "shimmed" using Webpack's ``exports-loader``.
- If your page touched any javascript modules that are used
  by pages that haven’t yet been migrated, test at least one of those
  non-migrated pages.
- Check if your base template has any descendants that should also be migrated.

Troubleshooting
---------------

Troubleshooting migration issues
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When debugging Webpack issues, the first question is whether or not
the page you’re on has been migrated. You can find out by checking the
value of ``window.USE_WEBPACK`` in the browser console or ``window.USE_REQUIREJS``
if the page is still using RequireJS. If neither values return ``true``, then
the page has not been migrated yet.

Common issues on Webpack pages:

- JS error like
  ``$(...).something is not a function``: this indicates there’s a missing
  dependency. Typically “something” is either ``select2`` or a jQuery UI
  widget like ``datepicker``. To fix, add the missing dependency to the
  module that’s erroring.
- Missing functionality, but no error: this
  usually indicates a missing knockout binding. To fix, add the file
  containing the binding to the module that applies that binding, which
  usually means adding ``hqwebapp/js/knockout_bindings.ko`` to the page’s entry point.
- JS error like ``something is not defined`` where
  ``something`` is one of the parameters in the module’s main function:
  this can indicate a circular dependency. This is rare in HQ. Track down
  the circular dependency and see if it makes sense to eliminate it by
  reorganizing code. If it doesn’t work, you can use
  `hqRequire <https://github.com/dimagi/commcare-hq/commit/15b436f77875f57d1e3d8d6db9b990720fa5dd6f#diff-73c73327e873d0e5f5f4e17c3251a1ceR100>`__
  to require the necessary module at the point where it’s used rather than
  at the top of the module using it.
- JS error like ``x is not defined``
  where ``x`` is a third-party module, which is the dependency of another
  third party module ``y`` and both of them are not modules. You
  may get this intermittent error when you want to use ``y`` in the
  migrated module and ``x`` and ``y`` is not formatted as a recognizable JavaScript module that
  Webpack recognizes (AMD, ESM, CommonJS are supported formats). You can fix this by adding
  an ``exports-loader`` ``rule`` `like this example <https://github.com/dimagi/commcare-hq/blob/e0b722c61e63b5878759d545282178ae374695e9/webpack/webpack.common.js#L70-L80>`__.

Common issues on non-Bundled pages:

- JS error like
  ``something is not defined`` where ``something`` is a third-party
  module: this can happen if a non-Bundled page uses a Bundled module
  which uses a third party module based on a global variable. There’s some
  code that mimics AMD modules in this situation, but it needs to know
  about all of the third party libraries. To fix, add the third party
  module’s global to `thirdPartyMap in
  hqModules.js <https://github.com/dimagi/commcare-hq/commit/85286460a8b08812f82d6709c161b259e77165c4#diff-73c73327e873d0e5f5f4e17c3251a1ceR57>`__.
- JS error like ``something is not defined`` where ``something`` is an
  HQ module: this can happen when script tags are ordered so that a module
  appears before one of its dependencies. This can happen to migrated
  modules because one of the effects of the migration is to typically
  import all of a module’s dependencies at the time the module is defined,
  which in a non-bundled context means all of the dependencies’ script
  tags must appear before the script tags that depend on them. Previously,
  dependencies were not imported until ``hqImport`` was called, which
  could be later on, possibly in an event handler or some other code that
  would never execute until the entire page was loaded. To fix, try
  reordering the script tags. If you find there’s a circular dependency,
  use ``hqRequire`` as described above.

Troubleshooting the RequireJS build process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::
    This is here for informational purposes only and will be removed once
    all of the RequireJS code is moved to Webpack.

Tactics that can help track down problems with the RequireJS build
process, which usually manifest as errors that happen on staging but not
locally:

-  To turn off minification, you can run ``build_requirejs`` with the
   ``--no_optimize`` option. This also makes the script run much faster.
-  To stop using the CDN, comment out `resource_versions.js in
   hqwebapp/base.html <https://github.com/dimagi/commcare-hq/pull/18116/files#diff-1ecb20ffccb745a5c0fc279837215a25R433>`__.
   Note that this will still fetch a few files, such as ``hqModules.js``
   and ``{bootstrap_version}/requirejs_config.js``, from the CDN. To turn off the CDN
   entirely, comment out all of the code that manipulates
   ``resource_versions`` in
   `build_requirejs <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/hqwebapp/management/commands/build_requirejs.py>`__.
-  To mimic the entire build process locally:

   -  Collect static files: ``manage.py collectstatic --noinput`` This
      is necessary if you’ve made any changes to ``{bootstrap_version}/requirejs.yml`` or
      ``{bootstrap_version}/requirejs_config.js``, since the build script pulls these files
      from ``staticfiles``, not ``corehq``.
   -  Compile translation files: ``manage.py compilejsi18n``
   -  Run the build script: ``manage.py build_requirejs --local``

      -  This will **overwrite** your local versions of
         ``{bootstrap_version}/requirejs_config.js`` and ``resource_versions.js``, so be
         cautious running it if you have uncommitted changes.
      -  This will also copy the generated bundle files from
         ``staticfiles`` back into ``corehq``.
      -  If you don’t need to test locally but just want to see the
         results of dependency tracing, leave off the ``--local``. A
         list of each bundle’s contents will be written to
         ``staticfiles/build.txt``, but no files will be added to or
         overwritten in ``corehq``.
