External Packages
=================

This page discusses how to add new dependencies with yarn.

Be cautious of adding new dependencies, which introduce an indefinite maintenance burden.

Do **not** add packages via script tags. An external package's documentation may show
how to include it via script tags, for the sake of getting up and running quickly.
This is fine to do in development. However, when added to production,
packages should be installed via yarn. Virtually any package that would be added to HQ 
will be on `NPM <https://www.npmjs.com/>`_. In rare cases, we also include packages 
directly from GitHub, as described below. Using yarn enables tooling to do things like 
scan for outdated versions and for packages with recently discovered CVEs.

Yarn
----

Yarn can manage components that contain HTML, CSS, JavaScript, fonts or
even image files. Yarn doesn’t concatenate or minify code or do anything
else - it just installs the right versions of the packages you need and
their dependencies.

Yarn packages
~~~~~~~~~~~~~

Yarn packages can be installed from a variety of sources, including a
registered yarn package (a repo that has a ``package.json`` file
defined), a Github shorthand (``<user or org>/<repo_name>``), a Github
URL, or just a plain URL that points to a javascript file.

When you install a package, it will be installed in a directory called
``node_modules``. For example if you were to run ``yarn add jquery``,
you would find a directory ``node_modules/jquery``.

Specifying packages in ``package.json``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To ensure a package gets installed for a project, you must specify it in
the ``package.json`` file. This is equivalent to the
``requirements.txt`` file for ``pip``. Similar to ``pip install`` for
python, for yarn, use ``yarn upgrade`` When specifying a yarn package
you can use many techniques. Here are a few examples:

.. code:: js

   // Installs the jquery package at version 1.11.1 to `node_modules/jquery`
   "jquery": "1.11.1"

   // Because `jquery-other` does not refer to a yarn package we must specify it in the
   // versioning. Yarn will install this package to `node_modules/jquery-other`.
   "jquery-other": "npm:jquery#1.2.0"

   // This will install jquery from a github hash
   "jquery-github": "jquery/jquery#44cb97e0cfc8d3e62bef7c621bfeba6fe4f65d7c"

To generalize, an install declaration looks like this:

::

   <name>:<package>#<version>

Where ``<package>`` is optional if ``<name> == <package>``. A package
can be any of these things:

======================= ===================================
Type                    Example
======================= ===================================
Registered package name jquery
Git endpoint            https://github.com/user/package.git
Git shorthand           user/repo
URL                     http://example.com/script.js
======================= ===================================

There are more, but those are the important ones. Find the others
`here <https://classic.yarnpkg.com/en/docs/package-json>`__

A version can be any of these things:

============= =================
Type          Example
============= =================
semver        ``#1.2.3``
version range ``#~1.2.3``
Git tag       ``#<git tag>``
Git commit    ``#<commit sha>``
Git branch    ``#<branch>``
============= =================

Using Yarn packages in HQ
~~~~~~~~~~~~~~~~~~~~~~~~~

To use these packages in HQ, you can typically just import the name of the package.
The library's ``package.json`` will have a ``main`` attribute that will signal to
Webpack which code to include.

Importing the library names rather than a specific file is more robust to library upgrades.

In ESM modules:

::

    import DOMPurify from "DOMPurify";

In modules using ``hqDefine``:

::

    hqDefine("my_app/js/my_module", [
        "DOMPurify",
    ], function (
        DOMPurify,
    ) {
