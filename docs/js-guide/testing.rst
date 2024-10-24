Testing
=======

Best Practices
--------------

Writing good tests in javascript is similar to writing good tests in any
other language. There are a few best practices that are more pertinent
to javascript testing.

Mocking
~~~~~~~

When mocks are needed, use the ``sinon.js`` framework.

Setup
-----

In order to run the javascript tests you’ll need to install the required
npm packages:

::

   $ yarn install --frozen-lockfile

It’s recommended to install grunt globally in order to use grunt from
the command line:

::

   $ npm install -g grunt
   $ npm install -g grunt-cli

In order for the tests to run the **development server needs to be
running on port 8000**.

Test Organization
-----------------

HQ’s JavaScript tests are organized around django apps. Test files are
stored in the django app they test. Tests infrastructure is stored in
its own django app, ``mocha``.

Most django apps with JavaScript tests have a single set of tests. These
will have an HTML template in
``corehq/apps/<app_name>/templates/<app_name>/spec/mocha.html``, which
inherits from the `mocha app’s base
template <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/mocha/templates/mocha/base.html>`__.
Test cases are stored in
``corehq/apps/<app_name>/static/<app_name>/js/spec/<test_suite_name>_spec.js``

A few django apps have multiple test “configs” that correspond to
different templates. Each config template will be in
``corehq/apps/<app>/templates/<app>/spec/<config>/mocha.html`` and its
tests will be in
``corehq/apps/<app_name>/static/<app_name>/<config>/spec/``. These are
defined in ``Gruntfile.js`` as ``<app_name>/<config_name>``, e.g.,
``cloudcare/form_entry``.


Running tests from the command line
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To run the javascript tests for a particular app run:

::

   $ grunt test:<app_name> // (e.g. grunt test:app_manager)

To list all the apps available to run:

::

   $ grunt list

Running tests from the browser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To run a django app’s tests from the browser, visit this url:

::

   http://localhost:8000/mocha/<app_name>

To run a specific config:

::

   http://localhost:8000/mocha/<app_name>/<config>  // (e.g. http://localhost:8000/mocha/cloudcare/form_entry)

Adding a new app or config
~~~~~~~~~~~~~~~~~~~~~~~~~~

There are three steps to adding a new app:

1. Add the django app name to the ``Gruntfile.js`` file.
2. Create a mocha template in
   ``corehq/apps/<app>/templates/<app>/spec/mocha.html`` to run tests.
   See an example on
   `here <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/app_manager/templates/app_manager/spec/mocha.html>`__.
3. Create tests that are included in the template in
   ``corehq/apps/<app>/static/<app>/spec/``

To add an additional config to an existing app, specify the app in the
``Gruntfile.js`` like this:

::

   <app_name>/<config>  // (e.g. cloudcare/form_entry)

The template and tests then also being in config-specific directories,
as described above.
