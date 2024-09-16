Updating Module Syntax from AMD to ESM
======================================

Most entry points for legacy modules that have recently been migrated from RequireJS to
Webpack as part of the `RequireJS to Webpack Migration
<https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/requirejs-to-webpack.rst>`__
are eligible for this update.

See the `Historical Background on Module Patterns
<https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/module-history.rst>`__
for a more detailed discussion of module types. As a quick refresher, here are some definitions:

AMD (Asynchronous Module Definition)
    The legacy module type used for older JavaScript modules on HQ.
    This was the only module type compatible with RequireJS, our first JavaScript bundler.
    It is still needed as a format for modules required by No-Bundler pages.

ESM (ES Modules)
    The newest module type with updated powerful import and export syntax. This is the module
    format that you will see referenced by documentation in modern javascript frameworks.

The different types of modules you will encounter are:

Entry Point Modules
    Modules that are included directly on a page using a bundler template tag, like
    ``webpack_main``. These are the modules that the bundler (Webpack) uses to build
    a dependency graph so that it knows what bundle of javascript dependencies and
    page-specific code is needed to render that page / entry point.

Dependency Modules
    These are modules that are never referenced in a bundler template tag and are only
    in the list of dependencies for other modules. Often these modules are used as utility modules
    or a way to organize JavaScript for a page that is very front-end heavy.


Step 1: Determine if the Module is Eligible for a Syntax Update
---------------------------------------------------------------

The HQ AMD-style module will look something like:

::

    hqDefine('hqwebapp/js/my_module', [
        'jquery',
        'knockout',
        'underscore',
        'hqwebapp/js/initial_page_data',
        'hqwebapp/js/assert_properties',
        'hqwebapp/js/bootstrap5/knockout_bindings.ko',
        'commcarehq',
    ], function (
        $,
        ko,
        _,
        initialPageData,
        assertProperties
    ) {
        ...
    });


Entry Points
~~~~~~~~~~~~

If this module is a webpack entry point, then it is eligible for an update. In the example above, you would find
``hqwebapp/js/my_module`` used on a page with the following:

::

    {% webpack_main "hqwebapp/js/my_module %}

The entry point can also be specified with ``webpack_main_b3`` if the module is part of the Bootstrap 3 build
of Webpack.

If this module is inside a ``requirejs_main`` or ``requirejs_main_b5`` tag, then it is NOT eligible for an update.
Instead, please first
`migrate this module from RequireJS to Webpack <https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/requirejs-to-webpack.rst>`__

Dependency Modules
~~~~~~~~~~~~~~~~~~

If this module is a dependency of any modules that are ``requirejs_main`` entry points, then this module is not
eligible for migration. If a module's syntax is updated when it's still required by RequireJS modules, then
it will result in a RequireJS build failure on deploy.

If this module is referenced by any ``hqImport`` calls (for instance ``hqImport('hqwebapp/js/my_module')``),
then this module is NOT yet eligible, and must continue using the older AMD-style syntax until
the ``hqImport`` statements are no longer needed. See the
`JS Bundler Migration Guide <https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/migrating.rst>`__ for
how to proceed in this case.

Slightly Different Syntax
~~~~~~~~~~~~~~~~~~~~~~~~~

If the AMD-style module looks a bit different than the syntax above--for instance, the list of dependencies are missing or
``hqImport`` and/or global variables can be found in the main body of the module--then this module must be
`migrated to use a JS Bundler <https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/migrating.rst>`__.


Step 2: Update Surrounding Module Structure
-------------------------------------------

ESM no longer needs to define the module name within the module itself. Instead, Webpack (our bundler) is configured
to know how to reference this module by its filename and relative path within an application.

You can start this by changing:

::

    hqDefine('hqwebapp/js/my_module', [
        'jquery',
        'knockout',
        'underscore',
        'hqwebapp/js/initial_page_data',
        'hqwebapp/js/assert_properties',
        'hqwebapp/js/bootstrap5/knockout_bindings.ko',
        'commcarehq',
    ], function (
        $,
        ko,
        _,
        initialPageData,
        assertProperties
    ) {
        ...
    });

to

::

    [
        'jquery',
        'knockout',
        'underscore',
        'hqwebapp/js/initial_page_data',
        'hqwebapp/js/assert_properties',
        'hqwebapp/js/bootstrap5/knockout_bindings.ko',
        'commcarehq',
    ] (
        $,
        ko,
        _,
        initialPageData,
        assertProperties
    )
    // additionally, the indentation for the module-specific code can be updated
    ...

Step 3: Update Dependency Imports
---------------------------------

Common ``yarn`` dependencies can now be referenced by their NPM name (or the alias defined in
``webpack/webpack.common.js``.

The same can be done with named internal dependencies, or referenced internal dependencies.

The final module dependency structure will look something like:

::

    import "commcarehq";  // Note: moved to top

    // named yarn/npm dependencies
    import $ from "jquery";
    import ko from "knockout";
    import _ from "underscore";

    // named internal dependencies:
    import initialPageData from "hqwebapp/js/initial_page_data";
    import assertProperties from "hqwebapp/js/assert_properties";

    // referenced internal dependencies:
    import "hqwebapp/js/bootstrap3/knockout_bindings.ko";

    // module specific code...
    ...

Note that ``import "commcarehq";`` has been moved to the top of the file. The ordering is
for consistency purposes, but it's important that either ``import "commcarehq";`` or
``import "commcarehq_b3";`` (for Bootstrap 3 / ``webpack_main_b3``) is present in the list
of imports for Webpack Entry Point modules.

Remember, an Entry Point is any module that is included directly on a page using the
``webpack_main`` or ``webpack_main_b3`` template tags.

Modules that are not entry points are not required to have this import. If you are updating the
syntax of a dependency (non-entry point) module, do not worry about including this import if
it is not already present.


Step 4: Other Code Updates
--------------------------

If this module is an entry point, then the rest of the module-specific code can remain as is,
with the indentation level updated. However, some entry points are also dependencies of other
entry points. If that's the case, proceed to the next part.

If this module is a dependency module, meaning it is referenced by other modules,
then the ``return`` line at the end of the module should follow the appropriate ``export`` syntax
needed by the modules that depend on this module.

The most likely change is to replace ``return`` with ``export`` and leave everything else as is.
Otherwise, see the
`export documentation <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/export>`__
for details and inspiration in case you want to do some additional refactoring.
