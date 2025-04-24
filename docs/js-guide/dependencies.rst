Managing Dependencies
=====================

Front-end dependencies are managed using ``yarn`` and are defined in ``package.json`` at the
root of the ``commcare-hq`` repository.

Most JavaScript on HQ is included on a page via a JavaScript bundle.
These bundles are created by Webpack. Webpack is given a list of "entry points"
(or pages) and builds a dependency graph of modules to determine what
code is needed for a page, combining related code into bundles.
These bundles are split along ``vendor`` (npm modules),
``common`` (all of hq), and application (like ``hqwebapp`` or ``domain``).

By bundling code, we can make fewer round-trip requests to fetch all of a page's JavaScript.
Additionally, the bundler minifies each bundle to reduce its overall size. You can learn
more about bundlers in `the Static Files Overview
<https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/static-files.rst#why-use-a-javascript-bundler>`__

A few areas of our codebase are also undergoing a migration toward using a bundler.
You can read more about this migration in the `JS Bundler Migration Guide
<https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/migration.rst>`__

Before adopting a bundler, HQ's javascript followed a more legacy, unstructured coding style
that relied on ordering script tags on a page. This approach required more individual
requests to fetch each dependency separately. "Bundles" were created manually by grouping
script tags inside the ``compress`` template tag managed by Django Compressor.

If you are modifying code inside a section that still follows this structure, the way you
import external modules/dependencies for use in that page's code will differ from the module
approach on pages using Webpack. We will address this legacy approach at the end of this chapter.


How do I create a new page with JavaScript?
-------------------------------------------

New code should be written using the ES Module (ESM) format and bundled using Webpack. This approach
is oriented around a single "entry point" per page (with some pages sharing the same entry point).
This entry point contains the page-level logic needed for that page and imports other modules for shared logic.

A typical new module structure will look something like:

::

    import "commcarehq";  // REQUIRED at the top of every "entry point"
                          // This loads site-wide dependencies needed to run global navigation, modals, notifications, etc.

    // Common third-party dependencies
    import $ from "jquery";                     // Ideally, new pages should move away from jQuery and use native
                                                // javascript. But this is here as an example.
    import ko from "knockout";
    import "hqwebapp/js/knockout_bindings.ko";  // This one doesn't need a named parameter because it only adds
                                                // knockout bindings and is not referenced in this file
    import _ from "underscore";

    // A commonly used internal module for passing server-side data to the front end
    import initialPageData from "hqwebapp/js/initial_page_data";

    /* page-level entry point logic begins here */



To register your module as a Webpack entry point, add the ``js_entry`` template tag to your HTML template,
near the top and outside of any other block:

::

   {% js_entry 'prototype/js/example' %}

Some pages don't have any unique logic but do rely on other modules.
These are usually pages that use some common widgets but don't have custom UI interactions.

If your page only relies on a single JavaScript module, you can use that as that
page's entry point:

::

   {% js_entry 'locations/js/widgets' %}

If your page relies on multiple modules, it still needs one entry point.
You can handle this by making a module that only imports other modules.
For instance an entry point located at ``prototype/js/combined_example.js``
might look like:

::

    import "commcarehq";  // always at the top

    import "hqwebapp/js/crud_paginated_list_init";
    import "hqwebapp/js/bootstrap5/widgets";

    // No page-specific logic, just need to collect the dependencies above

Then in your HTML page:

::

   {% js_entry 'prototype/js/combined_example' %}

The exception to the above is if your page inherits from a legacy page that
doesn't use a JavaScript bundler, like in app manager. This is rare,
but one example would be adding a new page to app manager that inherits
from ``apps_base.html``.


Why is old code formatted differently?
--------------------------------------

Most older entry points are written in a modified AMD
style and should eventually be migrated to an ESM format.

However, be careful when migrating modified AMD modules that aren't entry points, as some of these modules,
like ``hqwebapp/js/initial_page_data``, are still being referenced by pages not using a JavaScript bundler.
These pages still require this modified AMD approach until they transition to using Webpack.

We will cover what common modified AMD modules look like in this section, but you can read more
about this choice of module format in the `Historical Background on Module Patterns
<https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/module-history.rst>`__

The process of migrating a module from AMD to ESM is very straightforward. To learn more,
please see `Migrating Modules from AMD to ESM
<https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/amd-to-esm.rst>`__


Modified AMD Legacy Modules
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modified AMD-style modules are used both on bundler pages and no-bundler pages.

To differentiate between the two, look at the module's ``hqDefine`` call at the top of the file.

Modules in this format used with Webpack will look like the following,
with all dependencies loaded as part of ``hqDefine``:

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

In no-bundler areas of the codebase, "transition" AMD modules look like the following,
having no dependency list and no function parameters.
Additionally, HQ modules are loaded using ``hqImport`` in the body, and third-party libraries aren't declared at all,
instead relying on globals like ``ko`` (for Knockout.js) in the example below.

::

   hqDefine("my_app/js/my_file", function () {
       var myObservable = ko.observable(hqImport("hqwebapp/js/initial_page_data").get("thing"));
       ...
   });


How do I know if I’m working with Webpack?
------------------------------------------------------------

You are likely working with Webpack.
However, one major areas has **not** been migrated: app manager.

The easiest way to determine if a page is using either Webpack is to
open the JavaScript console on that page and type ``window.USE_WEBPACK``, which will return
``true`` if the page is using Webpack. If it is undefined, then the page is
a no-bundler page.

ES Modules (ESM)
~~~~~~~~~~~~~~~~

If your page is using ESM, it is using Webpack, as no-bundler pages do
not use this module format.

ESM can quickly be identified by scanning the file for ``import`` statements like this:

::

    import myDependency from "hqwebapp/js/my_dependency";

    import { Modal } from "bootstrap5";


How do I add a new internal module or external dependency to an existing page?
------------------------------------------------------------------------------

Webpack supports multiple module formats, with ES Modules (ESM) being the preferred format.
New modules should be written in the ESM format.

That being said, a lot of legacy code on HQ is written in a modified AMD format.
If you are adding a lot of new code to such a module, it is recommended that you
`migrate this module to ESM format
<https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/amd-to-esm.rst>`__.
However, not every modified AMD module is ready to be migrated to ESM immediately,
so it's worth familiarizing yourself with working in that format.

The format of the module you add a dependency to will determine how you include that dependency.

ESM Module
~~~~~~~~~~

ESM modules provide an extensive and flexible away of managing and naming imports from dependencies.

::

    import myDependency from "hqwebapp/js/my_new_dependency";
    myDependency.myFunction();

    // using only portions of an dependency
    import { Modal } from "bootstrap5";
    const myModal = new Modal(document.getElementById('#myModal'));

    // this also works
    import bootstrap from "bootstrap5";
    const myOtherModal = new bootstrap.Modal(document.getElementById('#myOtherModal'));

    // you can also alias imports
    import * as myAliasedDep from "hqwebapp/js/my_other_dependency";


Modified AMD
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. warning::
    You should NOT create NEW modules with this style.

To use your new module/dependency, add it your module’s ``hqDefine`` list of dependencies.
If the new dependency will be directly referenced in the body of the module, also add a
parameter to the ``hqDefine`` callback:

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


No-Bundler Pages
~~~~~~~~~~~~~~~~

.. note::

    No-Bundler pages are pages that do not have a Webpack entry point.
    New pages should never be created without a ``js_entry`` entry point.

    Eventually, the remaining pages in this category will be modularized properly to integrate with Webpack
    as part of the `JS Bundler Migration
    <https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/migrating.rst>`__.

    Also note that these pages are **only** compatible with legacy modified AMD modules. ESM modules
    do not work here.

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

Do **not** add the dependency list and parameters from the modified AMD style or
use `hqImport` on ESM formatted modules. It's
easy to introduce bugs that won’t be visible until the module is
actually migrated, and migrations are harder when they have pre-existing
bugs. See the `troubleshooting section of the JS Bundler Migration
Guide <https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/migrating.rst#troubleshooting>`__
if you’re curious about the kinds of issues that crop up.


My python tests are failing because of javascript
-------------------------------------------------

Failures after "Building Webpack"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The JavaScript tests run in Github Actions ``yarn build`` to check that ``webpack`` is building
without errors. You can run ``yarn build`` locally to simulate any errors encountered by these tests.

Since you are likely developing using ``yarn dev``, you should have already encountered the
build errors during development. However, if the development build of Webpack is running
without failures, please check the ``webpack/webpack.prod.js`` configuration for possible
issues if the error messages don't yield anything useful.


My deploy is failing because of javascript
------------------------------------------

Webpack Failures
~~~~~~~~~~~~~~~~

Webpack failures during deploy should be rare if you were able to run ``yarn dev`` successfully
locally during development. However, if these failures do occur, it is likely due to
issues with supporting deployment infrastructure.

Is the version of ``npm`` and ``yarn`` up-to-date on the deploy machines? Are the supporting scripts
outlined in the staticfiles_collect tasks for `Webpack
<https://github.com/dimagi/commcare-cloud/blob/master/src/commcare_cloud/ansible/roles/deploy_hq/tasks/staticfiles_collect.yml>`__
configured properly?


How close are we to a world where we’ll just have one set of conventions?
-------------------------------------------------------------------------

As above, most code is migrated, but most of the remaining areas have
significant complexity.

`hqDefine.sh <https://github.com/dimagi/commcare-hq/blob/master/scripts/codechecks/hqDefine.sh>`__
generates metrics for the current status of the migration and locates
un-migrated files. At the time of writing:

::

    $ ./scripts/codechecks/hqDefine.sh

98%     (1352/1386) of HTML files are free of inline scripts
97%     (533/555) of non-ESM JS files use hqDefine
92%     (506/555) of non-ESM JS files specify their dependencies
98%     (1355/1386) of HTML files are free of script tags
13%     (82/637) of JS files use ESM format
