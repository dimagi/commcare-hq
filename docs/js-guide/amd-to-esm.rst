Updating Module Syntax from AMD to ESM
======================================

Most javascript files are eligible for this update.

Here are some definitions:

AMD (Asynchronous Module Definition)
    The legacy module type used for older JavaScript modules on HQ, identified by having a ``define``
    statement near the top of the file.

ESM (ES Modules)
    The newest module type with updated powerful import and export syntax. This is the module
    format that you will see referenced by documentation in modern javascript frameworks.
    This is quickly identified by the ``import`` statements at the top used for including dependencies.

The different types of modules you will encounter are:

Entry Point Modules
    Modules that are included directly on a page using a bundler template tag, like
    ``js_entry``. These are the modules that the bundler (Webpack) uses to build
    a dependency graph so that it knows what bundle of javascript dependencies and
    page-specific code is needed to render that page / entry point.

Dependency Modules
    These are modules that are never referenced by ``js_entry`` and are only
    in the list of dependencies for other modules. Often these modules are used as utility modules
    or a way to organize JavaScript for a page that is very front-end heavy.


Step 1: Determine if the Module is Eligible for a Syntax Update
---------------------------------------------------------------

The HQ AMD-style module will look something like:

::

    define('hqwebapp/js/my_module', [
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

    {% js_entry "hqwebapp/js/my_module %}

The entry point can also be specified with ``js_entry_b3`` if the module is part of the Bootstrap 3 build
of Webpack.

Step 2: Update the Module Syntax
--------------------------------

Key Points
~~~~~~~~~~

-   ESM no longer needs to define the module name within the module itself. Instead, Webpack (our bundler) is configured
    to know how to reference this module by its filename and relative path within an application.
-   By default, you can use the same dependency names with the ``import`` syntax. If the ``import`` statement results
    in a Webpack Build error, look at ``webpack.common.js`` because it might require an alias.

Automation
~~~~~~~~~~

As a first step, you can run the `amd_to_esm <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/hqwebapp/management/commands/amd_to_esm.py>`__
management command, which will rewrite the file in place, replacing the ``define`` call with a series of
``import`` statements.


Example Structural Change
~~~~~~~~~~~~~~~~~~~~~~~~~

This is a rough example of what the changes will look like:

::

    define('hqwebapp/js/my_module', [
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

    import "commcarehq";  // Note: moved to top

    // named yarn/npm dependencies
    import $ from "jquery";
    import ko from "knockout";
    import _ from "underscore";

    // named internal dependencies:
    import initialPageData from "hqwebapp/js/initial_page_data";
    import assertProperties from "hqwebapp/js/assert_properties";

    // unnamed internal dependencies:
    import "hqwebapp/js/bootstrap3/knockout_bindings.ko";

    // module specific code...
    ...

Note that ``import "commcarehq";`` has been moved to the top of the file. The ordering is
for consistency purposes, but it's important that either ``import "commcarehq";`` is present in the list
of imports for Webpack Entry Point modules. If this import is not present in an entry point,
then site-wide navigation, notifications, modals, and other global widgets will not
work on that page.

Remember, an Entry Point is any module that is included directly on a page using the
``js_entry`` or ``js_entry_b3`` template tags.

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
