Managing Dependencies
=====================

HQ’s JavaScript is being gradually migrated from a legacy, unstructured
coding style the relies on the ordering of script tags to instead use
RequireJS for dependency management. This means that dependencies are
managed differently depending on which area of the code you’re working
in. This page is a developer’s guide to understanding which area you’re
working in and what that means for your code.

How do I know whether or not I’m working with RequireJS?
--------------------------------------------------------

You are likely working with RequireJS, as most of HQ has been migrated.
However, several major areas have **not** been migrated: app manager,
reports, and web apps. Test code also does not currently use RequireJS;
see
`Testing <https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/testing.rst>`__
for working with tests.

To tell for sure, look at your module’s ``hqDefine`` call, at the top of
the file.

RequireJS modules look like this, with all dependencies loaded as part
of ``hqDefine``:

::

   hqDefine("my_app/js/my_file", [
       "knockout",
       "hqwebapp/js/initial_page_data"
   ], function (
       ko,
       initialPageData
   ) {
       var myObservable = ko.observable(initialPageData.get("thing"));
       ...
   });

Non-RequireJS modules look like this, with no list and no function
parameters. HQ modules are loaded using ``hqImport`` in the body, and
third party libraries aren’t declared at all, instead relying on
globals:

::

   hqDefine("my_app/js/my_file", function () {
       var myObservable = ko.observable(hqImport("hqwebapp/js/initial_page_data").get("thing"));
       ...
   });

How do I write a new page?
--------------------------

New code should be written in RequireJS, which is oriented around a
single “entry point” into the page.

Most pages have some amount of logic only relevant to that page, so they
have a file that includes that logic and then depends on other modules
for shared logic.

`data_dictionary.js <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/data_dictionary/static/data_dictionary/js/data_dictionary.js>`__
fits this common pattern:

::

   hqDefine("data_dictionary/js/data_dictionary", [    // Module name must match filename
       "jquery",                                       // Common third-party dependencies
       "knockout",
       "underscore",
       "hqwebapp/js/initial_page_data",                // Dependencies on HQ files always match the file's path
       "hqwebapp/js/main",
       "analytix/js/google",
       "hqwebapp/js/knockout_bindings.ko",             // This one doesn't need a named parameter because it only adds
                                                       // knockout bindings and is not referenced in this file
   ], function (
       $,                                              // These common dependencies use these names for compatibility
       ko,                                             // with non-requirejs pages, which rely on globals
       _,
       initialPageData,                                // Any dependency that will be referenced in this file needs a name.
       hqMain,
       googleAnalytics
   ) {
       /* Function definitions, knockout model definitions, etc. */

       var dataUrl = initialPageData.reverse('data_dictionary_json');  // Refer to dependencies by their named parameter
       ...

       $(function () {
           /* Logic to run on documentready */
       });

       // Other code isn't going to depend on this module, so it doesn't return anything or returns 1
   });

To register your module as the RequireJS entry point, add the
``requirejs_main`` template tag to your HTML page, near the top but
outside of any other block:

::

   {% requirejs_main 'data_dictionary/js/data_dictionary' %}

Some pages don’t have any unique logic but do rely on other modules.
These are usually pages that use some common widgets but don’t have
custom UI interactions.

If your page only relies on a single js module, you can use that as the
module’s entry point:

::

   {% requirejs_main 'locations/js/widgets' %}

If your page relies on multiple modules, it still needs one entry point.
You can handle this by making a module that has no body, just a set of
dependencies, like in
`gateway_list.js <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/static/sms/js/gateway_list.js>`__:

::

   hqDefine("sms/js/gateway_list", [
       "hqwebapp/js/crud_paginated_list_init",
       "hqwebapp/js/bootstrap3/widgets",
   ], function () {
       // No page-specific logic, just need to collect the dependencies above
   });

Then in your HTML page:

::

   {% requirejs_main 'sms/js/gateway_list' %}

The exception to the above is if your page inherits from a page that
doesn’t use RequireJS. This is rare, but one example would be adding a
new page to app manager that inherits from ``managed_app.html``.

How do I add a new dependency to an existing page?
--------------------------------------------------

RequireJS
~~~~~~~~~

Add the new module to your module’s ``hqDefine`` list of dependencies.
If the new dependency will be directly referenced in the body of the
module, also add a parameter to the ``hqDefine`` callback:

::

   hqDefine("my_app/js/my_module", [
       ...
       "hqwebapp/js/my_new_dependency",
   ], function (
       ...,
       myDependency
   ) {
       ...
       myDependency.myFunction();
   });

Non-RequireJS
~~~~~~~~~~~~~

In your HTML template, add a script tag to your new dependency. Your
template likely already has scripts included in a ``js`` block:

::

   {% block js %}{{ block.super }}
     ...
     <script src="{% static 'hqwebapp/js/my_new_dependency.js' %}"></script>
   {% endblock js %}

In your JavaScript file, use ``hqImport`` to get access to your new
dependency:

::

   hqDefine("my_app/js/my_module", function () {
       ...
       var myDependency = hqImport("hqwebapp/js/my_new_dependency");
       myDependency.myFunction();
   });

Do **not** add the RequireJS-style dependency list and parameters. It’s
easy to introduce bugs that won’t be visible until the module is
actually migrated, and migrations are harder when they have pre-existing
bugs. See the `troubleshooting section of the RequireJS Migration
Guide <https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/migrating.rst#troubleshooting>`__
if you’re curious about the kinds of issues that crop up.

How close are we to a world where we’ll just have one set of conventions?
-------------------------------------------------------------------------

As above, most code is migrated, but most of the remaining areas have
significant complexity.

`hqDefine.sh <https://github.com/dimagi/commcare-hq/blob/master/scripts/codechecks/hqDefine.sh>`__
generates metrics for the current status of the migration and locates
umigrated files. At the time of writing:

::

   $ ./scripts/codechecks/hqDefine.sh

   98%     (825/843) of HTML files are free of inline scripts
   88%     (375/427) of JS files use hqDefine
   59%     (249/427) of JS files specify their dependencies
   91%     (765/843) of HTML files are free of script tags

Why aren’t we using something more fully-featured, more modern, or cooler than RequireJS?
-----------------------------------------------------------------------------------------

This migration began quite a while ago. At the time, the team discussed
options and selected RequireJS. The majority of the work done to move to
RequireJS has been around reorganizing code into modules and explicitly
declaring dependencies, which would be necessary for any kind of modern
dependency management. We are not permanently wedded to RequireJS,
although it is unlikely that we will migrate to another tool while a
significant amount of code is still in the legacy state.
