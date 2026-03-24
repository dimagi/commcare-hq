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


How do I add a new internal module or external dependency to an existing page?
------------------------------------------------------------------------------

ESM modules provide an extensive and flexible way of managing and naming imports from dependencies.

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
