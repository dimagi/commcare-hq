Migrating RequireJS to Webpack
==============================

RequireJS `reached its end of life <https://github.com/requirejs/requirejs/issues/1816#issuecomment-707503323>`__
in September of 2020. Since then, it has been increasingly difficult to work with as more modern libraries
no longer provide AMD modules (the preferred module format of RequireJS), and use modern JavaScript
syntax that is no longer compatible with RequireJS's build process. We decided to use Webpack as our
replacement for RequireJS in September of 2024. We expect the migration to be brief and straightforward.


Overview of the Process
-----------------------

The following steps outline the migration process on a per entry point basis.

As a reminder, Entry Points are modules that are included directly on a page using a bundler template tag,
like the ones listed below. We want to migrate the RequireJS entry points to Webpack entry points:

 - ``requirejs_main_b5`` to ``js_entry``
 - ``requirejs_main`` to ``js_entry_b3``

Entry points are the modules that the bundler (RequireJS or Webpack) uses to build a dependency graph so
that it knows what bundle of javascript dependencies and page-specific code is needed to render that page.
See `the Static Files Overview <https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/static-files.rst>`__
for a more detailed explanation.

.. note::

    If new ``exports-loader`` statements are added, it is recommended to test the changes on staging to ensure
    the functionality is maintained between production and staging.

Step 0: Decide What to Migrate
------------------------------

How do you know what areas have and have not been migrated? Because all pages that bundle javascript use a template
tag to specify the entry point, this template tag is an easy way to tell if a page uses Webpack or RequireJS.

If looking for areas that **need** to be migrated, grepping for ``requirejs_main`` will identify all unmigrated
pages.


Step 1: Update the Template Tag and Add Global ``commcarehq`` Dependency
------------------------------------------------------------------------

First, find either the ``requirejs_main`` tag (Bootstrap 3 pages) or the ``requirejs_main_b5`` tag
(Bootstrap 5 pages) that references the entry point you want to migrate.

The migration of an entry point from RequireJS to Webpack will involve updating the template tag
used to define the entry point and then adding the ``commcarehq`` global dependency to the list of dependencies.
Two examples are below.

Bootstrap 5 Entry Points
~~~~~~~~~~~~~~~~~~~~~~~~

In the ``case_importer/js/main`` example from Step 1, we can update the ``requirejs_main_b5`` template tag
to ``js_entry``, so that the final usage looks like:

::

    {% js_entry "case_importer/js/main" %}

Then, in the file itself, we add the ``commcarehq`` dependency to the list of dependencies:

::

    hqDefine("case_importer/js/main", [
        'jquery',
        'underscore',
        'hqwebapp/js/initial_page_data',
        'case_importer/js/import_history',
        'case_importer/js/excel_fields',
        'hqwebapp/js/bootstrap5/widgets',
        'commcarehq',  // <--- dependency added for webpack
    ], function (
        $,
        _,
        initialPageData,
        importHistory,
        excelFieldsModule
    ) {
        ...

`Here is an example commit of a migrated Bootstrap 5 entry point
<https://github.com/dimagi/commcare-hq/pull/35186/commits/029854e14ef08ef29d87293da5970bf35fb5ffca>`__.


Bootstrap 3 Entry Points
~~~~~~~~~~~~~~~~~~~~~~~~

In the ``domain/js/my_project_settings`` example from Step 1, we can update the ``requirejs_main``
tag to ``js_entry_b3``, so that the final usage looks like:

::

    {% js_entry_b3 "domain/js/my_project_settings" %}

Then, in the file itself, we add the ``commcarehq_b3`` dependency to the list of dependencies:

::

    hqDefine("domain/js/my_project_settings", [
        'jquery',
        'knockout',
        'hqwebapp/js/initial_page_data',
        'commcarehq_b3',  // <--- dependency added for webpack
    ], function (
        $,
        ko,
        initialPageData
    ) {
        ...

`Here is an example commit of a migrated Bootstrap 3 entry point
<https://github.com/dimagi/commcare-hq/pull/35186/commits/9153f3cedc550b518f537bc6783d06754fd35577>`__.


Step 2: Verify Webpack Build
----------------------------

The next step is to ensure that the Webpack build succeeds with the newly-added
entry point. To do this, restart or run ``yarn dev`` locally. If the build fails,
it is likely due to a missing alias or application folder path.

If it is a missing alias for a ``yarn`` dependency, first check to if the
dependency being referenced is using the ``npm`` package name (or ``npm_modules`` filepath)
or if it referring to an alias previously specified in the ``requirejs_config`` files.
Ideally, try to use the ``npm`` package/path and update the references for the dependency (if possible).
If not, you can add the alias in ``webpack/webpack.common.js``.

If an application path is missing, for instance it can't find a path to a dependency
that is under ``<app_name>/js/<path>``, then it might be that there are no entry points
in that app yet. If this is the case, add the ``<app_name>`` to the
``alwaysIncludeApps`` list in ``webpack/generateDetails.js``. Eventually, this list
won't be necessary once everything is migrated, but for now that's the best workaround.

Once these points are updated, please restart ``yarn dev``. If more build errors persist,
please see the troubleshooting guide below. If there is no help there, please reach out
the lead developers in charge of this migration for assistance. Please add troubleshooting
guidance afterward.

Once the build succeeds, please commit all the changes for that entry point.


Step 3: Verify Page Loads Without JavaScript Errors
---------------------------------------------------

The final step is to ensure that the page with the Entry Point loads without
JavaScript errors. Most of the time, entry points should load without errors if
the build succeeds.

If there are JavaScript errors, the mostly likely issue is due to ``undefined`` errors
when referencing a module/dependency. The most likely cause of this is a missing
``exports-loader`` statement for a dependency that was previously shimmed in the
``requirejs_config`` files. See the `documentation for exports-loader
<https://webpack.js.org/loaders/exports-loader/>`__ on how to do this, or follow
existing patterns of ``exports-loader`` statements for dependencies that were shimmed
in ``requirejs_config`` similarly to the dependency you are having issues with now.

Please add any additional guidance here as the migration continues.
